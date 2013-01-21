"""
REST API annotations resource.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


import re

from flask import abort, current_app, g, jsonify, url_for

from ... import db
from ...models import Annotation
from ... import tasks
from ..errors import ValidationError
from ..security import has_role, owns_annotation, owns_data_source
from .base import TaskedResource


class AnnotationsResource(TaskedResource):
    """
    An annotation is represented as an object with the following fields:

    * **uri** (`string`) - URI for this annotation.
    * **original_data_source_uri** (`string`) - URI for the original :ref:`data source <api_data_sources>`.
    * **annotated_data_source_uri** (`string`) - URI for the annotated :ref:`data source <api_data_sources>`.
    * **written** (`boolean`) - Whether or not this annotation has been written.
    """
    model = Annotation
    instance_name = 'annotation'
    instance_type = 'annotation'

    task = tasks.write_annotation

    views = ['list', 'get', 'add']

    filterable = {'data_source': 'data_source'}

    list_ensure_conditions = [has_role('admin'), owns_data_source]
    list_ensure_options = {'satisfy': any}

    get_ensure_conditions = [has_role('admin'), owns_annotation]
    get_ensure_options = {'satisfy': any}

    add_ensure_conditions = [has_role('admin'), owns_data_source,
                             has_role('annotator'), has_role('trader')]
    add_ensure_options = {'satisfy': lambda conditions: next(conditions) or (next(conditions) and any(conditions))}
    add_schema = {'data_source': {'type': 'data_source', 'required': True},
                  'global_frequencies': {'type': 'boolean'},
                  'exclude_samples': {'type': 'list', 'schema': {'type': 'sample'}},
                  'include_samples': {'type': 'list',
                                      'schema': {'type': 'list',
                                                 'items': [{'type': 'string'},
                                                           {'type': 'sample'}]}}}

    def add_view(self, data_source, global_frequencies=False,
                 exclude_samples=None, include_samples=None):
        # Todo: Check if data source is a VCF file.
        # Todo: The `include_samples` might be better structured as a list of
        #     objects, e.g. ``[{label: GoNL, sample: ...}, {label: 1KG, sample: ...}]``.
        # The `satisfy` keyword argument used here in the `ensure` decorator means
        # that we ensure at least one of:
        # - admin
        # - owns_data_source AND annotator
        # - owns_data_source AND trader
        exclude_samples = exclude_samples or []

        # Todo: Perhaps a better name would be `local_frequencies` instead of
        #     `include_sample_ids`, to contrast with the `global_frequencies`
        #     flag.
        include_samples = dict(include_samples or [])

        if not all(re.match('[0-9A-Z]+', label) for label in include_samples):
            raise ValidationError('Labels for inluded samples must contain only'
                                  ' uppercase alphanumeric characters')

        for sample in include_samples.values():
            if not (sample.public or
                    sample.user is g.user or
                    'admin' in g.user.roles):
                # Todo: Meaningful error message.
                abort(400)

        if 'admin' not in g.user.roles and 'annotator' not in g.user.roles:
            # This is a trader, so check if the data source has been imported in
            # an active sample.
            # Todo: Anyone should be able to annotate against the public samples.
            if not data_source.variations.join(Sample).filter_by(active=True).count():
                raise InvalidDataSource('inactive_data_source', 'Data source '
                    'cannot be annotated unless it is imported in an active sample')

        annotated_data_source = DataSource(g.user,
                                           '%s (annotated)' % data_source.name,
                                           data_source.filetype,
                                           empty=True, gzipped=True)
        db.session.add(annotated_data_source)
        annotation = Annotation(data_source, annotated_data_source)
        db.session.add(annotation)
        db.session.commit()
        current_app.logger.info('Added data source: %r', annotated_data_source)
        current_app.logger.info('Added annotation: %r', annotation)

        result = tasks.write_annotation.delay(annotation.id,
                                              global_frequencies=global_frequencies,
                                              exclude_sample_ids=[sample.id for sample in exclude_samples],
                                              include_sample_ids={label: sample.id for label, sample in include_samples.items()})
        current_app.logger.info('Called task: write_annotation(%d) %s', annotation.id, result.task_id)
        uri = url_for('.annotation_get', annotation=annotation.id)
        response = jsonify(annotation_uri=uri)
        response.location = uri
        return response, 202

    def serialize(self, resource, embed=None):
        serialization = super(AnnotationsResource, self).serialize(resource, embed=embed)
        serialization.update(original_data_source_uri=url_for('.data_source_get', data_source=resource.original_data_source_id),
                             annotated_data_source_uri=url_for('.data_source_get', data_source=resource.annotated_data_source_id),
                             written=resource.task_done)
        return serialization
