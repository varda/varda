"""
REST API variations resource.

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
                  'data_source': {'type': 'data_source', 'required': True}}

    @classmethod
    def serialize(cls, resource, embed=None):
        serialization = super(VariationsResource, cls).serialize(resource, embed=embed)
        serialization.update(sample_uri=url_for('.sample_get', sample=resource.sample_id),
                             data_source_uri=url_for('.data_source_get', data_source=resource.data_source_id),
                             imported=resource.task_done)
        return serialization
