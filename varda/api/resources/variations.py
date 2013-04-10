"""
REST API variations model resource.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from flask import url_for

from ...models import Variation
from ... import tasks
from ..security import has_role, owns_sample, owns_variation
from .base import TaskedResource
from .data_sources import DataSourcesResource
from .samples import SamplesResource


class VariationsResource(TaskedResource):
    """
    A set of observations is represented as an object with the following fields:

    * **uri** (`string`) - URI for this set of observations.
    * **sample_uri** (`string`) - URI for the :ref:`sample <api_samples>`.
    * **data_source_uri** (`string`) - URI for the :ref:`data source <api_data_sources>`.
    * **imported** (`boolean`) - Whether or not this set of observations is imported.
    """
    model = Variation
    instance_name = 'variation'
    instance_type = 'variation'

    task = tasks.import_variation

    views = ['list', 'get', 'add']

    embeddable = {'data_source': DataSourcesResource, 'sample': SamplesResource}
    filterable = {'sample': 'sample'}

    list_ensure_conditions = [has_role('admin'), owns_sample]
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

    @classmethod
    def list_view(cls, *args, **kwargs):
        """
        Get a collection of sets of observations.

        Requires the `admin` role or being the owner of the sample.

        :statuscode 200: Respond with a list of :ref:`set of observations <api_variations>`
            objects as `variations`.

        Example request:

        .. sourcecode:: http

            GET /variations HTTP/1.1

        Example response:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
              "variations":
                [
                  {
                    "uri": "/variations/11",
                    "sample_uri": "/samples/3",
                    "data_source_uri": "/data_sources/26"
                    "imported": true
                  },
                  {
                    "uri": "/variations/12",
                    "sample_uri": "/samples/4",
                    "data_source_uri": "/data_sources/27"
                    "imported": true
                  }
                ]
            }
        """
        return super(VariationsResource, cls).list_view(*args, **kwargs)

    @classmethod
    def get_view(cls, *args, **kwargs):
        """
        Get details for a set of observations.

        Requires the `admin` role or being the owner of the set of
        observations.

        :statuscode 200: Respond with a :ref:`set of observations <api_variations>`
            object as `variation` and if importing is ongoing its progress in
            percentages as `progress`.

        Example request:

        .. sourcecode:: http

            GET /variations/12 HTTP/1.1

        Example response:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
              "variation":
                {
                  "uri": "/variations/12",
                  "sample_uri": "/samples/4",
                  "data_source_uri": "/data_sources/27"
                  "imported": false
                },
              "progress": 78
            }
        """
        return super(VariationsResource, cls).get_view(*args, **kwargs)

    @classmethod
    def add_view(cls, *args, **kwargs):
        """
        Create a set of observations.

        Requires the `admin` role or being the owner of the sample.

        :arg sample: URI for the sample to import the set of observations to.
        :type sample: string
        :arg data_source: URI for the data source to read the set of observations from.
        :type data_source: string
        :statuscode 202: Respond with a URI for the created set of
            observations as `variation_uri`.

        Example request:

        .. sourcecode:: http

            POST /variations HTTP/1.1
            Content-Type: application/json

            {
              "sample": "/samples/14",
              "data_source": "/data_sources/18"
            }

        Example response:

        .. sourcecode:: http

            HTTP/1.1 202 Accepted
            Location: https://example.com/variations/3
            Content-Type: application/json

            {
              "variation_uri": "/variations/3"
            }
        """
        return super(VariationsResource, cls).add_view(*args, **kwargs)

    @classmethod
    def serialize(cls, instance, embed=None):
        serialization = super(VariationsResource, cls).serialize(instance, embed=embed)
        serialization.update(imported=instance.task_done)
        return serialization
