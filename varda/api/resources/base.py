"""
REST API resources.

This module defines some base classes for resource definitions. The standard
:class:`Resource` base class implements just the `get` view in a general way.

A :class:`ModelResource` definition is parameterized by an SQLAlchemy model,
where a resource instance provides views on the model instances. In addition
to the `get` view, this class implements the `list`, `add`, and `edit` views.
The definition can be made more specific for a model by overriding the views
in a resource subclass.

The :class:`TaskedResource` base class provides the same for models where
creating a model instance implies running a Celery task. To this end, the
`add` view implements running a specified task and the `get` view provides
information about the state of the task.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from functools import wraps

import celery.exceptions
from flask import current_app, jsonify, url_for

from ... import db
from ... import tasks
from ..data import data
from ..security import ensure, has_role
from ..utils import collection


# Todo: We implement the different resources here with inheritance. If we at
#    some point want to factor out the resource stuff into some sort of small
#    REST framework, it might be better to change this to composition.
#    The superclasses and subclasses are quite tightly coupled and especially
#    in a library setting this wouldn't work very well since the interface
#    offered by the superclasses is unclear. See, for example, [1].
#
# [1] https://github.com/mcdonc/apidesign/blob/master/presentation.rst#4-composinginheriting


class Resource(object):
    """
    Base class for a REST resource definition.

    General implementation is provided for the **get** view on the resource.
    """
    instance_name = None
    instance_type = None

    views = ['get']

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

    #: Can be one of `string`, `int`, `float`, `path`. See `URL Route
    #: Registrations in Flask
    #: <http://flask.pocoo.org/docs/api/#url-route-registrations>`_.
    key_type = 'int'

    def __new__(cls, *args, **kwargs):
        cls.list_rule = '/'
        cls.get_rule = '/<%s:%s>' % (cls.key_type, cls.instance_name)
        cls.add_rule = '/'
        cls.edit_rule = '/<%s:%s>' % (cls.key_type, cls.instance_name)

        id_schema = {cls.instance_name: {'type': cls.instance_type, 'id': True}}
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
        @data(**getattr(self, '%s_schema' % endpoint))
        @ensure(*getattr(self, '%s_ensure_conditions' % endpoint),
                **getattr(self, '%s_ensure_options' % endpoint))
        @wrapper
        def view(*args, **kwargs):
            return view_func(*args, **kwargs)

        self.blueprint.add_url_rule('%s%s' % (self.url_prefix or '/', getattr(self, '%s_rule' % endpoint)),
                                    '%s_%s' % (self.instance_name, endpoint),
                                    view,
                                    **kwargs)

    @classmethod
    def get_view(cls, embed=None, **kwargs):
        instance = kwargs.get(cls.instance_name)
        return jsonify({cls.instance_name: cls.serialize(instance, embed=embed)})

    @classmethod
    def instance_key(cls, instance):
        """
        To be implemented by a subclass. Should return something of type
        `cls.key_type`.
        """
        raise NotImplementedError

    @classmethod
    def collection_uri(cls):
        return url_for('.%s_list' % cls.instance_name)

    @classmethod
    def instance_uri(cls, instance):
        return cls.instance_uri_by_key(cls.instance_key(instance))

    @classmethod
    def instance_uri_by_key(cls, key):
        return url_for('.%s_get' % cls.instance_name,
                       **{cls.instance_name: key})

    @classmethod
    def serialize(cls, instance, embed=None):
        embed = embed or []
        serialization = {'uri': cls.instance_uri(instance)}
        for field, resource in cls.embeddable.items():
            if field in embed:
                s = resource.serialize(getattr(instance, field))
            else:
                # Note: By default (i.e., without embedding), we don't want
                #     to have an extra query for the embedded resource, which
                #     is what happens if we would write `instance.field.id`.
                #     So we make sure we really write `instance.field_id`.
                # Todo: Only do this in `ModelResource`.
                # Note: We rely on the convention that relationships in our
                #     models are defined such that the foreign key field is
                #     the relationship name with ``_id`` suffix.
                key = field + '_id'
                s = {'uri': resource.instance_uri_by_key(getattr(instance,
                                                                 key))}
            serialization.update({field: s})
        return serialization


class ModelResource(Resource):
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

    views = ['list', 'get', 'add', 'edit']

    @classmethod
    def list_view(cls, begin, count, embed=None, **filter):
        # Todo: Explicitely order resources in the collection, possibly in a
        #     user-defined way.
        #     Since we are using LIMIT/OFFSET, it is very important that we
        #     use ORDER BY as well [1]. It might be the case that we already
        #     implicitely have ORDER BY clauses on our queries [2], and if
        #     not, we at least have the option to define a default ORDER BY
        #     in the model definition [3].
        #     Also not that LIMIT/OFFSET may get slow on many rows [1], so
        #     perhaps it's worth considering a recipe like [4] or [5] as an
        #     alternative.
        #
        # [1] http://www.postgresql.org/docs/8.0/static/queries-limit.html
        # [2] http://www.mail-archive.com/sqlalchemy@googlegroups.com/msg07314.html
        # [3] https://groups.google.com/forum/?fromgroups=#!topic/sqlalchemy/mhMPaKNQYyc
        # [4] http://www.sqlalchemy.org/trac/wiki/UsageRecipes/WindowedRangeQuery
        # [5] http://stackoverflow.com/questions/6618366/improving-offset-performance-in-postgresql
        instances = cls.model.query
        if filter:
            instances = instances.filter_by(**filter)
        items = [cls.serialize(r, embed=embed)
                 for r in instances.limit(count).offset(begin)]
        return (instances.count(),
                jsonify(collection={'uri': cls.collection_uri(),
                                    'items': items}))

    @classmethod
    def add_view(cls, *args, **kwargs):
        instance = cls.model(**kwargs)
        db.session.add(instance)
        db.session.commit()
        current_app.logger.info('Added %s: %r', cls.instance_name, instance)
        response = jsonify({cls.instance_name: cls.serialize(instance)})
        response.location = cls.instance_uri(instance)
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
    def instance_key(cls, instance):
        return instance.id


class TaskedResource(ModelResource):
    """
    Base class for a REST resource definition based on an SQLAlchemy model
    where creating a model instance is followed by running a Celery task.
    """
    task = None

    @classmethod
    def edit_view(cls, *args, **kwargs):
        if kwargs.pop('task', None) == {}:
            if not 'admin' in g.user.roles:
                # Todo: Better error message.
                abort(403)
            instance = kwargs[cls.instance_name]
            # Todo: This has a possible race condition, but I'm not bothered
            #     to fix it at the moment. Reading and setting task_uuid
            #     should be an atomic action.
            #     An alternative would be to use real atomic locking, e.g.
            #     using redis [1].
            # [1] http://ask.github.com/celery/cookbook/tasks.html#ensuring-a-task-is-only-executed-one-at-a-time
            if instance.task_uuid:
                result = cls.task.AsyncResult(instance.task_uuid)
                if result.state in ('STARTED', 'PROGRESS'):
                    abort(403)
                result.revoke()
            instance.task_done = False
            result = cls.task.delay(instance.id)
            instance.task_uuid = result.task_id
            db.session.commit()
        return super(TaskedResource, cls).edit_view(*args, **kwargs)

    @classmethod
    def add_view(cls, *args, **kwargs):
        instance = cls.model(**kwargs)
        db.session.add(instance)
        db.session.commit()
        current_app.logger.info('Added %s: %r', cls.instance_name, instance)

        # Note: We have to store the task id at the caller side, since we want
        #     it available also while the task is not running yet. I.e., we
        #     cannot set `instance.task_uuid` from within the task itself.
        result = cls.task.delay(instance.id)
        instance.task_uuid = result.task_id
        db.session.commit()
        current_app.logger.info('Called task: %s(%d) %s', cls.task.__name__, instance.id, result.task_id)

        response = jsonify({cls.instance_name: cls.serialize(instance)})
        response.location = cls.instance_uri(instance)
        return response, 201

    @classmethod
    def serialize(cls, instance, embed=None):
        serialization = super(TaskedResource, cls).serialize(instance, embed=embed)
        task = {'done': instance.task_done}
        if instance.task_uuid:
            result = cls.task.AsyncResult(instance.task_uuid)
            task.update(state=result.state.lower())
            if result.state == 'PROGRESS':
                task.update(progress=result.info.get('percentage'))
            if result.state == 'FAILURE' and isinstance(result.result, tasks.TaskError):
                task.update(error={'code': result.result.code,
                                   'message': result.result.message})
        serialization.update(task=task)
        return serialization
