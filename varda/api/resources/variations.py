"""
REST API variations model resource.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from flask import url_for

from ...models import Variation
from ... import tasks
from ..security import has_role, owns_sample, owns_variation, public_sample
from .base import TaskedResource
from .data_sources import DataSourcesResource
from .samples import SamplesResource


class VariationsResource(TaskedResource):
    """
    Variation resources model sets of variant observations.

    A variation resource is a :ref:`tasked resource <api-tasked-resources>`.
    The associated server task is importing the variation data from the linked
    data source in the server database.
    """
    model = Variation
    instance_name = 'variation'
    instance_type = 'variation'

    task = tasks.import_variation

    views = ['list', 'get', 'add', 'edit', 'delete']

    embeddable = {'data_source': DataSourcesResource, 'sample': SamplesResource}
    filterable = {'sample': 'sample'}

    list_ensure_conditions = [has_role('admin'), owns_sample, public_sample]
    list_ensure_options = {'satisfy': any}

    get_ensure_conditions = [has_role('admin'), owns_variation]
    get_ensure_options = {'satisfy': any}

    add_ensure_conditions = [has_role('admin'), owns_sample]
    add_ensure_options = {'satisfy': any}
    add_schema = {'sample': {'type': 'sample', 'required': True},
                  'data_source': {'type': 'data_source', 'required': True},
                  'skip_filtered': {'type': 'boolean'},
                  'use_genotypes': {'type': 'boolean'},
                  'prefer_genotype_likelihoods': {'type': 'boolean'}}

    delete_ensure_conditions = [has_role('admin'), owns_variation]
    delete_ensure_options = {'satisfy': any}

    @classmethod
    def serialize(cls, instance, embed=None):
        """
        A variation is represented as an object with the following fields:

        **uri** (`uri`)
          URI for this resource.

        **task** (`object`)
          Task information, see :ref:`api-tasked-resources`.

        **data_source** (`object`)
          :ref:`Link <api-links>` to a :ref:`data source
          <api-resources-data-sources-instances>` resource (embeddable).

        **sample** (`object`)
          :ref:`Link <api-links>` to a :ref:`sample
          <api-resources-samples-instances>` resource (embeddable).
        """
        return super(VariationsResource, cls).serialize(instance, embed=embed)

    @classmethod
    def list_view(cls, *args, **kwargs):
        """
        Returns a collection of variations in the `variation_collection`
        field.

        .. note:: Requires one or more of the following:

           - Having the `admin` role.
           - Being the owner of the sample specified by the `sample` filter.
           - Setting the `sample` filter to a public sample.

        **Available filters:**

        - **sample** (`uri`)
        """
        return super(VariationsResource, cls).list_view(*args, **kwargs)

    @classmethod
    def get_view(cls, *args, **kwargs):
        """
        Returns the variation representation in the `variation` field.

        .. note:: Requires having the `admin` role or being the owner of the
           variation.
        """
        return super(VariationsResource, cls).get_view(*args, **kwargs)

    @classmethod
    def add_view(cls, *args, **kwargs):
        """
        Adds a variation resource.

        .. note:: Requires having the `admin` role or being the owner of the
           sample specified by the `sample` field.

        **Required request data:**

        - **data_source** (`uri`)
        - **sample** (`uri`)
        """
        return super(VariationsResource, cls).add_view(*args, **kwargs)

    @classmethod
    def edit_view(cls, *args, **kwargs):
        """
        Updates a variation resource.

        .. note:: Requires having the `admin` role.

        **Accepted request data:**

        - **task** (`object`)
        """
        return super(VariationsResource, cls).edit_view(*args, **kwargs)

    @classmethod
    def delete_view(cls, *args, **kwargs):
        """
        Todo: documentation, including how/if we cascade.
        """
        return super(VariationsResource, cls).delete_view(*args, **kwargs)
