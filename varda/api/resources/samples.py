"""
REST API samples resource.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from flask import g, url_for

from ...models import Sample
from ..security import is_user, has_role, owns_sample, true
from .base import Resource


class SamplesResource(Resource):
    """
    A sample is represented as an object with the following fields:

    * **uri** (`string`) - URI for this sample.
    * **user_uri** (`string`) - URI for the sample :ref:`owner <api_users>`.
    * **name** (`string`) - Human readable name.
    * **pool_size** (`integer`) - Number of individuals.
    * **public** (`boolean`) - Whether or not this sample is public.
    * **added** (`string`) - Date and time this sample was added.

    .. autoflask:: varda:create_app()
       :endpoints: api.sample_list, api.sample_get, api.sample_add, api.sample_edit
    """
    model = Sample
    instance_name = 'sample'
    instance_type = 'sample'

    filterable = {'public': 'boolean',
                  'user': 'user'}

    list_ensure_conditions = [has_role('admin'), is_user, true('public')]
    list_ensure_options = {'satisfy': any}

    get_ensure_conditions = [has_role('admin'), owns_sample]
    get_ensure_options = {'satisfy': any}

    add_ensure_conditions = [has_role('admin'), has_role('importer')]
    add_ensure_options = {'satisfy': any}
    add_schema = {'name': {'type': 'string', 'required': True},
                  'pool_size': {'type': 'integer'},
                  'coverage_profile': {'type': 'boolean'},
                  'public': {'type': 'boolean'}}

    edit_ensure_conditions = [has_role('admin'), owns_sample]
    edit_ensure_options = {'satisfy': any}
    edit_schema = {'active': {'type': 'boolean'},
                   'name': {'type': 'string'},
                   'pool_size': {'type': 'integer'},
                   'coverage_profile': {'type': 'boolean'},
                   'public': {'type': 'boolean'}}

    def add_view(self, **kwargs):
        kwargs['user'] = g.user
        return super(SamplesResource, self).add_view(**kwargs)

    # Todo: Document that active will be set to False.
    def edit_view(self, *args, **kwargs):
        if kwargs.get('active'):
            # Todo: Checks, e.g. if there are expected imported data sources
            # and no imports running at the moment. Also, number of coverage
            # tracks should be 0 or equal to pool size.
            #raise ActivationFailure('reason', 'This is the reason')
            pass
        else:
            # Todo: Always, even on name change?
            kwargs['active'] = False
        return super(SamplesResource, self).edit_view(**kwargs)

    def serialize(self, resource, embed=None):
        serialization = super(SamplesResource, self).serialize(resource, embed=embed)
        serialization.update(user_uri=url_for('.user_get', user=resource.user.id),
                             name=resource.name,
                             pool_size=resource.pool_size,
                             public=resource.public,
                             added=str(resource.added.isoformat()))
        return serialization
