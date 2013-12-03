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
    Sample resources model biological samples which can contain one or more
    individuals.
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
    def serialize(cls, instance, embed=None):
        """
        A sample is represented as an object with the following fields:

        **uri** (`uri`)
          URI for this resource.

        **active** (`boolean`)
          Whether or not this sample is active.

        **added** (`string`)
          Date and time this sample was added, see :ref:`api-datetime`.

        **coverage_profile** (`boolean`)
          Whether or not this sample has a coverage profile.

        **name** (`string`)
          Human readable sample name.

        **notes** (`string`)
          Human readable notes in Markdown format.

        **pool_size** (`integer`)
          Number of individuals in this sample.

        **public** (`boolean`)
          Whether or not this sample is public.

        **user** (`object`)
          :ref:`Link <api-links>` to a :ref:`user
          <api-resources-users-instances>` resource (embeddable).
        """
        serialization = super(SamplesResource, cls).serialize(instance, embed=embed)
        serialization.update(name=instance.name,
                             pool_size=instance.pool_size,
                             public=instance.public,
                             coverage_profile=instance.coverage_profile,
                             active=instance.active,
                             notes=instance.notes,
                             added=str(instance.added.isoformat()))
        return serialization

    @classmethod
    def list_view(cls, *args, **kwargs):
        """
        Returns a collection of samples in the `sample_collection` field.

        .. note:: Requires one or more of the following:

           - Having the `admin` role.
           - Being the user specified by the `user` filter.
           - Setting the `public` filter to `True`.

        **Available filters:**

        - **public** (`boolean`)
        - **user** (`uri`)

        **Orderable by:** `name`, `pool_size`, `public`, `active`, `added`
        """
        return super(SamplesResource, cls).list_view(*args, **kwargs)

    @classmethod
    def get_view(cls, *args, **kwargs):
        """
        Returns the sample representation in the `sample` field.

        .. note:: Requires one or more of the following:

           - Having the `admin` role.
           - Being the owner of the sample.
           - The sample is public.
        """
        return super(SamplesResource, cls).get_view(*args, **kwargs)

    @classmethod
    def add_view(cls, *args, **kwargs):
        """
        Adds a sample resource.

        .. note:: Requires having the `admin` or `importer` role.

        **Required request data:**

        - **name** (`string`)

        **Accepted request data:**

        - **coverage_profile** (`boolean`)
        - **notes** (`string`)
        - **pool_size** (`integer`)
        - **public** (`boolean`)
        """
        kwargs['user'] = g.user
        return super(SamplesResource, cls).add_view(*args, **kwargs)

    # Todo: Document that active will be set to False.
    @classmethod
    def edit_view(cls, *args, **kwargs):
        """
        Updates a sample resource.

        .. note:: Requires having the `admin` role or being the owner of the
           sample.

        **Accepted request data:**

        - **active** (`boolean`)
        - **coverage_profile** (`boolean`)
        - **name** (`string`)
        - **notes** (`string`)
        - **pool_size** (`integer`)
        - **public** (`boolean`)
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
        return super(SamplesResource, cls).edit_view(*args, **kwargs)

    @classmethod
    def delete_view(cls, *args, **kwargs):
        """
        Todo: documentation, including how/if we cascade.
        """
        return super(SamplersResource, cls).delete_view(*args, **kwargs)
