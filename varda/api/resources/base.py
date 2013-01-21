"""
REST API resources.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from functools import wraps

from flask import current_app, jsonify, url_for

from ... import db
from ..data import data
from ..security import ensure, has_role, require_user
from ..utils import collection


class Resource(object):
    model = None
    instance_name = None
    instance_type = None
    human_name = None

    views = ['list', 'get', 'add', 'edit']

    embeddable = {}
    filterable = {}

    list_ensure_conditions = [has_role('admin')]
    list_ensure_options = {}
    list_schema = {}

    get_ensure_conditions = [has_role('admin')]
    get_ensure_options = {}
    get_schema = {}

    add_ensure_conditions = [has_role('admin')]
    add_ensure_options = {}
    add_schema = {}

    edit_ensure_conditions = [has_role('admin')]
    edit_ensure_options = {}
    edit_schema = {}

    def __new__(cls, *args, **kwargs):
        cls.list_rule = '/'
        cls.get_rule = '/<int:%s>' % cls.instance_name
        cls.add_rule = '/'
        cls.edit_rule = '/<int:%s>' % cls.instance_name

        id_schema = {cls.instance_name: {'type': cls.instance_type}}
        cls.get_schema.update(id_schema)
        cls.edit_schema.update(id_schema)
        if cls.embeddable:
            embed_schema = {'embed': {'type': 'list', 'allowed': cls.embeddable.keys()}}
            cls.list_schema.update(embed_schema)
            cls.get_schema.update(embed_schema)
        if cls.filterable:
            filter_schema = {k: {'type': v} for k, v in cls.filterable.items()}
            cls.list_schema.update(filter_schema)
        return object.__new__(cls, *args, **kwargs)

    def __init__(self, blueprint, url_prefix=None):
        self.blueprint = blueprint
        self.url_prefix = url_prefix
        self.register_views()

    def register_views(self):
        if 'list' in self.views:
            self.register_view('list', wrapper=collection)
        if 'get' in self.views:
            self.register_view('get')
        if 'add' in self.views:
            self.register_view('add', methods=['POST'])
        if 'edit' in self.views:
            self.register_view('edit', methods=['PATCH'])

    def register_view(self, endpoint, wrapper=None, **kwargs):
        if wrapper is None:
            wrapper = lambda f: f

        view_func = getattr(self, '%s_view' % endpoint)

        @wraps(view_func)
        @require_user
        @data(**getattr(self, '%s_schema' % endpoint))
        @ensure(*getattr(self, '%s_ensure_conditions' % endpoint),
                **getattr(self, '%s_ensure_options' % endpoint))
        @wrapper
        def view(*args, **kwargs):
            return view_func(*args, **kwargs)

        self.blueprint.add_url_rule('%s%s' % (self.url_prefix or '/', getattr(self, '%s_rule' % endpoint)),
                                    '%s_%s' % (self.instance_type, endpoint),
                                    view,
                                    **kwargs)

    def list_view(self, begin, count, embed=None, **filter):
        # Todo: Just appending 's' to the result key to get plural here is
        #     very ugly.
        resources = self.model.query
        if filter:
            resources = resources.filter_by(**filter)
        return (resources.count(),
                jsonify({self.instance_name + 's': [self.serialize(r, embed=embed) for r in
                                                    resources.limit(count).offset(begin)]}))

    def get_view(self, embed=None, **kwargs):
        resource = kwargs.get(self.instance_name)
        return jsonify({self.instance_name: self.serialize(resource, embed=embed)})

    def add_view(self, *args, **kwargs):
        # Todo: Way to provide default values?
        resource = self.model(**kwargs)
        db.session.add(resource)
        db.session.commit()
        current_app.logger.info('Added %s: %r', self.instance_name, resource)
        uri = url_for('.%s_get' % self.instance_type, **{self.instance_name: resource.id})
        response = jsonify({'%s_uri' % self.instance_name: uri})
        response.location = uri
        return response, 201

    def edit_view(self, *args, **kwargs):
        resource = kwargs.pop(self.instance_name)
        for field, value in kwargs.items():
            setattr(resource, field, value)
        db.session.commit()
        current_app.logger.info('Updated %s: %r', self.instance_name, resource)
        return jsonify({self.instance_name: self.serialize(resource)})

    def serialize(self, resource, embed=None):
        """
        * **uri** (`string`) - URI for this resource.
        """
        embed = embed or []
        uri = url_for('.%s_get' % self.instance_type, **{self.instance_name: resource.id})
        serialization = {'uri': uri}
        serialization.update({field: self.embeddable[field].serialize(getattr(resource, field))
                              for field in embed})
        return serialization


class TaskedResource(Resource):
    task = None

    def get_view(self, embed=None, **kwargs):
        resource = kwargs.get(self.instance_name)
        progress = None
        if not resource.task_done and resource.task_uuid:
            result = self.task.AsyncResult(resource.task_uuid)
            try:
                # This re-raises a possible TaskError, handled by error_task_error
                # above.
                # Todo: Re-raising doesn't seem to work at the moment...
                result.get(timeout=3)
            except celery.exceptions.TimeoutError:
                pass
            if result.state == 'PROGRESS':
                progress = result.info['percentage']
        return jsonify({self.instance_name: self.serialize(resource, embed=embed), 'progress': progress})

    def add_view(self, *args, **kwargs):
        resource = self.model(**kwargs)
        db.session.add(resource)
        db.session.commit()
        current_app.logger.info('Added %s: %r', self.instance_name, resource)
        result = self.task.delay(resource.id)
        current_app.logger.info('Called task: %s(%d) %s', self.task.__name__, resource.id, result.task_id)
        uri = url_for('.%s_get' % self.instance_type, **{self.instance_name: resource.id})
        response = jsonify({'%s_uri' % self.instance_name: uri})
        response.location = uri
        return response, 202
