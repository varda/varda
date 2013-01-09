"""
REST API resources.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from flask import abort, jsonify, redirect, url_for

from .. import db
from ..models import (Annotation, Coverage, DataSource, DATA_SOURCE_FILETYPES,
                      Observation, Sample, User, USER_ROLES, Variation)
from .. import tasks
from .data import data
from .errors import ActivationFailure, ValidationError
from .security import (ensure, is_user, has_role, owns_annotation,
                       owns_coverage, owns_data_source, owns_sample,
                       owns_variation, true, require_user)
from .serialize import serialize
from .utils import collection, user_by_login


class Resource(object):
    model = None
    instance_name = None
    instance_type = None

    list_rule = '/'
    list_ensure_conditions = [has_role('admin')]
    list_ensure_options = {}
    list_schema = {}

    get_rule = None  # Defined in __new__
    get_ensure_conditions = [has_role('admin')]
    get_ensure_options = {}
    get_schema = None  # Defined in __new__

    add_rule = '/'
    add_ensure_conditions = [has_role('admin')]
    add_ensure_options = {}
    add_schema = {}

    def __new__(cls, *args, **kwargs):
        cls.get_rule = '/<int:%s>' % cls.instance_name
        cls.get_schema = {cls.instance_name: {'type': cls.instance_type}}
        return object.__new__(cls, *args, **kwargs)

    def __init__(self, app, url_prefix=None):
        self.app = app
        self.url_prefix = url_prefix
        self.register_views()

    def register_views(self):
        self.register_view('list', wrapper=collection)
        self.register_view('get')
        self.register_view('add', methods=['POST'])

    def register_view(self, endpoint, wrapper=None, **kwargs):
        if wrapper is None:
            wrapper = lambda f: f

        @require_user
        @data(**getattr(self, '%s_schema' % endpoint))
        @ensure(*getattr(self, '%s_ensure_conditions' % endpoint),
                **getattr(self, '%s_ensure_options' % endpoint))
        @wrapper
        def view_func(*args, **kwargs):
            return getattr(self, '%s_view' % endpoint)(*args, **kwargs)

        self.app.add_url_rule('%s%s' % (self.url_prefix or '/', getattr(self, '%s_rule' % endpoint)),
                              '%s_%s' % (self.instance_type, endpoint),
                              view_func,
                              **kwargs)

    def list_view(self, begin, count):
        resources = self.model.query
        return (resources.count(),
                jsonify(resources=[serialize(r) for r in
                                   resources.limit(count).offset(begin)]))

    def get_view(self, **kwargs):
        resource = kwargs.get(self.instance_name)
        return jsonify({self.instance_name: serialize(resource)})

    def add_view(self, *args, **kwargs):
        abort(501)


class UsersResource(Resource):
    model = User
    instance_name = 'user'
    instance_type = 'user'

    get_ensure_conditions = [has_role('admin'), is_user]
    get_ensure_options = {'satisfy': any}

    add_schema = {'login': {'type': 'string', 'minlength': 3, 'maxlength': 40,
                            'safe': True, 'required': True},
                  'name': {'type': 'string'},
                  'password': {'type': 'string', 'required': True},
                  'roles': {'type': 'list', 'allowed': USER_ROLES}}

    def add_view(self, login, password, name=None, roles=None):
        name = name or login
        roles = roles or []
        if User.query.filter_by(login=login).first() is not None:
            raise ValidationError('User login is not unique')
        user = User(name, login, password, roles)
        db.session.add(user)
        db.session.commit()
        self.app.logger.info('Added user: %r', user)
        uri = url_for('.user_get', user=user.id)
        response = jsonify(user_uri=uri)
        response.location = uri
        return response, 201
