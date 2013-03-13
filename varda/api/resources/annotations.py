"""
REST API annotations model resource.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


import re

from flask import abort, current_app, g, jsonify, url_for

from ... import db
from ...models import Annotation, DataSource, InvalidDataSource, Sample
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
                  'local_frequencies': {'type': 'list',
                                        'schema': {'type': 'dict',
                                                   'schema': {'label': {'type': 'string', 'required': True},
                                                              'sample': {'type': 'sample', 'required': True}}}},
                  'exclude_samples': {'type': 'list', 'schema': {'type': 'sample'}}}

    @classmethod
    def list_view(cls, *args, **kwargs):
        """
        Get a collection of annotations.

        Requires the `admin` role or being the owner of the data source.

        :statuscode 200: Respond with a list of :ref:`annotation <api_annotations>`
            objects as `annotations`.

        Example request:

        .. sourcecode:: http

            GET /annotations HTTP/1.1

        Example response:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
              "annotations":
                [
                  {
                    "uri": "/annotations/2",
                    "original_data_source_uri": "/data_sources/23",
                    "annotated_data_source_uri": "/data_sources/57",
                    "written": true
                  },
                  {
                    "uri": "/annotations/3",
                    "original_data_source_uri": "/data_sources/23",
                    "annotated_data_source_uri": "/data_sources/58",
                    "written": true
                  },
                  {
                    "uri": "/annotations/4",
                    "original_data_source_uri": "/data_sources/23",
                    "annotated_data_source_uri": "/data_sources/59",
                    "written": false
                  }
                ]
            }
        """
        return super(AnnotationsResource, cls).list_view(*args, **kwargs)

    @classmethod
    def get_view(cls, *args, **kwargs):
        """
        Get details for an annotation.

        Requires the `admin` role or being the owner of the annotation.

        :statuscode 200: Respond with an :ref:`annotation <api_annotations>`
            object as `annotation` and if writing is ongoing its progress in
            percentages as `progress`.

        Example request:

        .. sourcecode:: http

            GET /annotations/2 HTTP/1.1

        Example response:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
              "annotation":
                {
                  "uri": "/annotations/2",
                  "original_data_source_uri": "/data_sources/23",
                  "annotated_data_source_uri": "/data_sources/57",
                  "written": false
                },
              "progress": 98
            }
        """
        return super(AnnotationsResource, cls).get_view(*args, **kwargs)

    @classmethod
    def add_view(cls, data_source, global_frequencies=False,
                 local_frequencies=None, exclude_samples=None):
        """
        Create an annotation.

        .. todo:: Documentation.
        """
        # Todo: Check if data source is a VCF file.
        # The `satisfy` keyword argument used here in the `ensure` decorator means
        # that we ensure at least one of:
        # - admin
        # - owns_data_source AND annotator
        # - owns_data_source AND trader
        local_frequencies = local_frequencies or []
        exclude_samples = exclude_samples or []

        if not all(re.match('[0-9A-Z]+', frequency['label'])
                   for frequency in local_frequencies):
            raise ValidationError('Labels for local frequencies must contain only'
                                  ' uppercase alphanumeric characters')

        for frequency in local_frequencies:
            if not (frequency['sample'].public or
                    frequency['sample'].user is g.user or
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

        # Todo: If the task doesn't complete for some reason, we have no way
        #     to restart it since we don't store the parameters. Parameters
        #     should probably be stored in the Annotation model.
        result = tasks.write_annotation.delay(annotation.id,
                                              global_frequencies=global_frequencies,
                                              local_frequencies=[(frequency['label'], frequency['sample'].id)
                                                                 for frequency in local_frequencies],
                                              exclude_sample_ids=[sample.id for sample in exclude_samples])
        current_app.logger.info('Called task: write_annotation(%d) %s', annotation.id, result.task_id)
        uri = url_for('.annotation_get', annotation=annotation.id)
        response = jsonify(annotation_uri=uri)
        response.location = uri
        return response, 202

    @classmethod
    def serialize(cls, instance, embed=None):
        serialization = super(AnnotationsResource, cls).serialize(instance, embed=embed)
        serialization.update(original_data_source_uri=url_for('.data_source_get', data_source=instance.original_data_source_id),
                             annotated_data_source_uri=url_for('.data_source_get', data_source=instance.annotated_data_source_id),
                             written=instance.task_done)
        return serialization
