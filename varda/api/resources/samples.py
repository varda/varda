"""
REST API samples model resource.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from flask import g, url_for

from ...models import Sample
from ..security import is_user, has_role, owns_sample, public_sample, true
from .base import ModelResource
from .users import UsersResource


class SamplesResource(ModelResource):
    """
    A sample is represented as an object with the following fields:

    * **uri** (`string`) - URI for this sample.
    * **user_uri** (`string`) - URI for the sample :ref:`owner <api_users>`.
    * **name** (`string`) - Human readable name.
    * **pool_size** (`integer`) - Number of individuals.
    * **public** (`boolean`) - Whether or not this sample is public.
    * **added** (`string`) - Date and time this sample was added.
    """
    model = Sample
    instance_name = 'sample'
    instance_type = 'sample'

    views = ['list', 'get', 'add', 'edit', 'delete']

    embeddable = {'user': UsersResource}
    filterable = {'public': 'boolean',
                  'user': 'user'}
    orderable = ['name', 'pool_size', 'public', 'active', 'added']

    list_ensure_conditions = [has_role('admin'), is_user, true('public')]
    list_ensure_options = {'satisfy': any}

    get_ensure_conditions = [has_role('admin'), owns_sample, public_sample]
    get_ensure_options = {'satisfy': any}

    add_ensure_conditions = [has_role('admin'), has_role('importer')]
    add_ensure_options = {'satisfy': any}
    add_schema = {'name': {'type': 'string', 'required': True, 'maxlength': 200},
                  'pool_size': {'type': 'integer'},
                  'coverage_profile': {'type': 'boolean'},
                  'public': {'type': 'boolean'},
                  'notes': {'type': 'string', 'maxlength': 10000}}

    edit_ensure_conditions = [has_role('admin'), owns_sample]
    edit_ensure_options = {'satisfy': any}
    edit_schema = {'active': {'type': 'boolean'},
                   'name': {'type': 'string', 'maxlength': 200},
                   'pool_size': {'type': 'integer'},
                   'coverage_profile': {'type': 'boolean'},
                   'public': {'type': 'boolean'},
                   'notes': {'type': 'string', 'maxlength': 10000}}

    delete_ensure_conditions = [has_role('admin'), owns_sample]
    delete_ensure_options = {'satisfy': any}

    @classmethod
    def list_view(cls, *args, **kwargs):
        """
        Get a collection of samples.

        Requires one of the following:
         * the `admin` role
         * being the user specified in the `user` argument
         * the `public` argument set to ``True``

        :arg public: If set to ``True`` or ``False``, restrict the collection to
            public or non-public samples, respectively.
        :type public: boolean
        :arg user: If set to the URI for a user, restrict the collection to
            samples owned by this user.
        :type user: string
        :statuscode 200: Respond with a list of :ref:`sample <api_samples>`
            objects as `samples`.

        Example request:

        .. sourcecode:: http

            GET /samples?public=true HTTP/1.1

        Example response:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
              "samples":
                [
                  {
                    "uri": "/samples/3",
                    "user_uri": "/users/1",
                    "name": "1KG phase 1 release",
                    "pool_size": 1092,
                    "public": true,
                    "added": "2012-11-23T10:55:12.776706"
                  },
                  {
                    "uri": "/samples/4",
                    "user_uri": "/users/1",
                    "name": "GoNL SNP release 4",
                    "pool_size": 769,
                    "public": true,
                    "added": "2012-11-23T10:55:13.776706"
                  }
                ]
            }
        """
        return super(SamplesResource, cls).list_view(*args, **kwargs)

    @classmethod
    def get_view(cls, *args, **kwargs):
        """
        Get details for a sample.

        Requires the `admin` role or being the owner of the requested sample.

        :statuscode 200: Respond with a :ref:`sample <api_samples>` object as `sample`.

        Example request:

        .. sourcecode:: http

            GET /samples/3 HTTP/1.1

        Example response:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
              "sample":
                {
                  "uri": "/samples/3",
                  "user_uri": "/users/1",
                  "name": "1KG phase 1 release",
                  "pool_size": 1092,
                  "public": true,
                  "added": "2012-11-23T10:55:12.776706"
                }
            }
        """
        return super(SamplesResource, cls).get_view(*args, **kwargs)

    @classmethod
    def add_view(cls, **kwargs):
        """
        Create a sample

        Requires the `admin` or `importer` role.

        :arg name: Human readable name.
        :type name: string
        :arg pool_size: Number of individuals (default: ``1``).
        :type pool_size: integer
        :arg coverage_profile: Whether or not this sample has a coverage profile
            (default: ``True``).
        :type coverage_profile: boolean
        :arg public: Whether or not this sample is public (default: ``False``).
        :type public: boolean
        :statuscode 201: Respond with a URI for the created sample as `sample_uri`.

        Example request:

        .. sourcecode:: http

            POST /samples HTTP/1.1
            Content-Type: application/json

            {
              "name": "1KG phase 1 release",
              "pool_size": 1092,
              "coverage_profile": false,
              "public": true
            }

        Example response:

        .. sourcecode:: http

            HTTP/1.1 201 Created
            Location: https://example.com/samples/13
            Content-Type: application/json

            {
              "samples_uri": "/samples/13"
            }
        """
        kwargs['user'] = g.user
        return super(SamplesResource, cls).add_view(**kwargs)

    # Todo: Document that active will be set to False.
    @classmethod
    def edit_view(cls, *args, **kwargs):
        """
        Update a sample.

        Requires the `admin` role or being the owner of the requested sample.

        :arg active: If set to ``True`` or ``False``, activate or de-activate the
            sample, respectively.
        :type active: boolean
        :arg name: Human readable name.
        :type name: string
        :arg pool_size: Number of individuals (default: ``1``).
        :type pool_size: integer
        :arg coverage_profile: Whether or not this sample has a coverage profile
            (default: ``True``).
        :type coverage_profile: boolean
        :arg public: Whether or not this sample is public (default: ``False``).
        :type public: boolean
        :statuscode 200: Respond with a :ref:`sample <api_samples>` object as
            `sample`.

        Example request:

        .. sourcecode:: http

            PATCH /samples/14 HTTP/1.1
            Content-Type: application/json

            {
              "active": true
            }

        Example response:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
              "sample":
                {
                  "uri": "/samples/14",
                  "user_uri": "/users/1",
                  "name": "1KG phase 1 release",
                  "pool_size": 1092,
                  "public": true,
                  "added": "2012-11-23T10:55:12.776706"
                }
            }
        """
        if kwargs.get('active'):
            # Todo: Checks, e.g. if there are expected imported data sources
            # and no imports running at the moment. Also, number of coverage
            # tracks should be 0 or equal to pool size.
            #raise ActivationFailure('reason', 'This is the reason')
            pass
        else:
            # Todo: Always, even on name change?
            kwargs['active'] = False
        return super(SamplesResource, cls).edit_view(**kwargs)

    @classmethod
    def serialize(cls, instance, embed=None):
        serialization = super(SamplesResource, cls).serialize(instance, embed=embed)
        serialization.update(name=instance.name,
                             pool_size=instance.pool_size,
                             public=instance.public,
                             coverage_profile=instance.coverage_profile,
                             active=instance.active,
                             notes=instance.notes,
                             added=str(instance.added.isoformat()))
        return serialization
