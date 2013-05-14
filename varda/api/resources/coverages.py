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
    A set of regions is represented as an object with the following fields:

    * **uri** (`string`) - URI for this set of regions.
    * **sample_uri** (`string`) - URI for the :ref:`sample <api_samples>`.
    * **data_source_uri** (`string`) - URI for the :ref:`data source <api_data_sources>`.
    * **imported** (`boolean`) - Whether or not this set of regions is imported.
    """
    model = Coverage
    instance_name = 'coverage'
    instance_type = 'coverage'

    task = tasks.import_coverage

    views = ['list', 'get', 'add', 'edit']

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

    @classmethod
    def list_view(cls, *args, **kwargs):
        """
        Get a collection of sets of regions.

        Requires the `admin` role or being the owner of the sample.

        :statuscode 200: Respond with a list of :ref:`set of regions <api_coverages>`
            objects as `coverages`.

        Example request:

        .. sourcecode:: http

            GET /coverages HTTP/1.1

        Example response:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
              "coverages":
                [
                  {
                    "uri": "/coverages/11",
                    "sample_uri": "/samples/3",
                    "data_source_uri": "/data_sources/24"
                    "imported": true
                  },
                  {
                    "uri": "/coverages/12",
                    "sample_uri": "/samples/4",
                    "data_source_uri": "/data_sources/25"
                    "imported": true
                  }
                ]
            }
        """
        return super(CoveragesResource, cls).list_view(*args, **kwargs)

    @classmethod
    def get_view(cls, *args, **kwargs):
        """
        Get details for a set of regions.

        Requires the `admin` role or being the owner of the set of regions.

        :statuscode 200: Respond with a :ref:`set of regions <api_coverages>`
            object as `coverage` and if importing is ongoing its progress in
            percentages as `progress`.

        Example request:

        .. sourcecode:: http

            GET /coverages/12 HTTP/1.1

        Example response:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
              "coverage":
                {
                  "uri": "/coverages/12",
                  "sample_uri": "/samples/4",
                  "data_source_uri": "/data_sources/25"
                  "imported": false
                },
              "progress": 14
            }
        """
        return super(CoveragesResource, cls).get_view(*args, **kwargs)

    @classmethod
    def add_view(cls, *args, **kwargs):
        """
        Create a set of regions.

        Requires the `admin` role or being the owner of the sample.

        :arg sample: URI for the sample to import the set of regions to.
        :type sample: string
        :arg data_source: URI for the data source to read the set of regions from.
        :type data_source: string
        :statuscode 202: Respond with a URI for the created set of regions
            as `coverage_uri`.

        Example request:

        .. sourcecode:: http

            POST /coverages HTTP/1.1
            Content-Type: application/json

            {
              "sample": "/samples/14",
              "data_source": "/data_sources/17"
            }

        Example response:

        .. sourcecode:: http

            HTTP/1.1 202 Accepted
            Location: https://example.com/coverages/3
            Content-Type: application/json

            {
              "coverage_uri": "/coverages/3"
            }
        """
        return super(CoveragesResource, cls).add_view(*args, **kwargs)
