"""
REST API coverages model resource.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from flask import url_for

from ...models import Coverage
from ... import tasks
from ..security import has_role, owns_coverage, owns_sample, public_sample
from .base import TaskedResource
from .data_sources import DataSourcesResource
from .samples import SamplesResource


class CoveragesResource(TaskedResource):
    """
    Coverage resources model sets of genomic regions having high enough
    coverage in sequencing to do variant calling.

    A coverage resource is a :ref:`tasked resource <api-tasked-resources>`.
    The associated server task is importing the coverage data from the linked
    data source in the server database.
    """
    model = Coverage
    instance_name = 'coverage'
    instance_type = 'coverage'

    task = tasks.import_coverage

    views = ['list', 'get', 'add', 'edit', 'delete']

    embeddable = {'data_source': DataSourcesResource, 'sample': SamplesResource}
    filterable = {'sample': 'sample'}

    list_ensure_conditions = [has_role('admin'), owns_sample, public_sample]
    list_ensure_options = {'satisfy': any}

    get_ensure_conditions = [has_role('admin'), owns_coverage]
    get_ensure_options = {'satisfy': any}

    add_ensure_conditions = [has_role('admin'), owns_sample]
    add_ensure_options = {'satisfy': any}
    add_schema = {'sample': {'type': 'sample', 'required': True},
                  'data_source': {'type': 'data_source', 'required': True}}

    delete_ensure_conditions = [has_role('admin'), owns_coverage]
    delete_ensure_options = {'satisfy': any}

    @classmethod
    def serialize(cls, instance, embed=None):
        """
        A coverage is represented as an object with the following fields:

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
        return super(CoveragesResource, cls).serialize(instance, embed=embed)

    @classmethod
    def list_view(cls, *args, **kwargs):
        """
        Returns a collection of coverages in the `coverage_collection` field.

        .. note:: Requires one or more of the following:

           - Having the `admin` role.
           - Being the owner of the sample specified by the `sample` filter.
           - Setting the `sample` filter to a public sample.

        **Available filters:**

        - **sample** (`uri`)
        """
        return super(CoveragesResource, cls).list_view(*args, **kwargs)

    @classmethod
    def get_view(cls, *args, **kwargs):
        """
        Returns the coverage representation in the `coverage` field.

        .. note:: Requires having the `admin` role or being the owner of the
           coverage.
        """
        return super(CoveragesResource, cls).get_view(*args, **kwargs)

    @classmethod
    def add_view(cls, *args, **kwargs):
        """
        Adds a coverage resource.

        .. note:: Requires having the `admin` role or being the owner of the
           sample specified by the `sample` field.

        **Required request data:**

        - **data_source** (`uri`)
        - **sample** (`uri`)
        """
        return super(CoveragesResource, cls).add_view(*args, **kwargs)

    @classmethod
    def edit_view(cls, *args, **kwargs):
        """
        Updates a coverage resource.

        .. note:: Requires having the `admin` role.

        **Accepted request data:**

        - **task** (`object`)
        """
        return super(CoveragesResource, cls).edit_view(*args, **kwargs)

    @classmethod
    def delete_view(cls, *args, **kwargs):
        """
        Todo: documentation, including how/if we cascade.
        """
        return super(CoveragesResource, cls).delete_view(*args, **kwargs)
