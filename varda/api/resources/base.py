"""
REST API resources.

A resource definition is parameterized with an SQLAlchemy model. A resource
instance provides views on the model instances.

This module defines some base classes for resource definitions. The standard
:class:`Resource` base class implements the `list`, `get`, `add`, and `edit`
views in a general way. This implementation can be made more specific for a
model by overriding the views in a resource subclass.

The :class:`TaskedResource` base class provides the same for models where
creating a model instance implies running a Celery task. To this end, the
`add` view implements running a specified task and the `get` view provides
information about the state of the task.

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
    """
    Base class for a REST resource definition based on an SQLAlchemy model.

    General implementations are provided for the following views on the
    resource:

    * **list** - Get a collection of model instances.
    * **get** - Get details for a model instance.
    * **add** - Add a model instance.
    * **edit** - Update a model instance.
    """
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
        return super(Resource, cls).__new__(cls, *args, **kwargs)

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

    @classmethod
    def list_view(cls, begin, count, embed=None, **filter):
        # Todo: Just appending 's' to the result key to get plural here is
        #     very ugly.
        instances = cls.model.query
        if filter:
            instances = instances.filter_by(**filter)
        return (instances.count(),
                jsonify({cls.instance_name + 's': [cls.serialize(r, embed=embed) for r in
                                                   instances.limit(count).offset(begin)]}))

    @classmethod
    def get_view(cls, embed=None, **kwargs):
        instance = kwargs.get(cls.instance_name)
        return jsonify({cls.instance_name: cls.serialize(instance, embed=embed)})

    @classmethod
    def add_view(cls, *args, **kwargs):
        # Todo: Way to provide default values?
        instance = cls.model(**kwargs)
        db.session.add(instance)
        db.session.commit()
        current_app.logger.info('Added %s: %r', cls.instance_name, instance)
        uri = url_for('.%s_get' % cls.instance_type, **{cls.instance_name: instance.id})
        response = jsonify({'%s_uri' % cls.instance_name: uri})
        response.location = uri
        return response, 201

    @classmethod
    def edit_view(cls, *args, **kwargs):
        instance = kwargs.pop(cls.instance_name)
        for field, value in kwargs.items():
            setattr(instance, field, value)
        db.session.commit()
        current_app.logger.info('Updated %s: %r', cls.instance_name, instance)
        return jsonify({cls.instance_name: cls.serialize(instance)})

    @classmethod
    def serialize(cls, instance, embed=None):
        embed = embed or []
        uri = url_for('.%s_get' % cls.instance_type, **{cls.instance_name: instance.id})
        serialization = {'uri': uri}
        serialization.update({field: cls.embeddable[field].serialize(getattr(instance, field))
                              for field in embed})
        return serialization


class TaskedResource(Resource):
    """
    Base class for a REST resource definition based on an SQLAlchemy model
    where creating a model instance is followed by running a Celery task.
    """
    task = None

    @classmethod
    def get_view(cls, embed=None, **kwargs):
        instance = kwargs.get(cls.instance_name)
        progress = None
        if not instance.task_done and instance.task_uuid:
            result = cls.task.AsyncResult(instance.task_uuid)
            try:
                # This re-raises a possible TaskError, handled by error_task_error
                # above.
                # Todo: Re-raising doesn't seem to work at the moment...
                result.get(timeout=3)
            except celery.exceptions.TimeoutError:
                pass
            if result.state == 'PROGRESS':
                progress = result.info['percentage']
        return jsonify({cls.instance_name: cls.serialize(instance, embed=embed), 'progress': progress})

    @classmethod
    def add_view(cls, *args, **kwargs):
        instance = cls.model(**kwargs)
        db.session.add(instance)
        db.session.commit()
        current_app.logger.info('Added %s: %r', cls.instance_name, instance)
        result = cls.task.delay(instance.id)
        current_app.logger.info('Called task: %s(%d) %s', cls.task.__name__, instance.id, result.task_id)
        uri = url_for('.%s_get' % cls.instance_type, **{cls.instance_name: instance.id})
        response = jsonify({'%s_uri' % cls.instance_name: uri})
        response.location = uri
        return response, 202
