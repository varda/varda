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
from ..security import has_role, is_user, owns_annotation, owns_data_source
from .base import TaskedResource
from .data_sources import DataSourcesResource


def _satisfy_add(conditions):
    is_admin, is_annotator, is_trader, owns_data_source = conditions
    if is_admin:
        return True
    if owns_data_source:
        return is_annotator or is_trader
    return False


class AnnotationsResource(TaskedResource):
    """
    Annotation resources model sets of variants annotated with observation
    frequencies.

    An annotation resource is a :ref:`tasked resource <api-tasked-resources>`.
    The associated server task is calculating frequencies on the linked
    original data source and writing the annotated data to the linked
    annotated data source.
    """
    model = Annotation
    instance_name = 'annotation'
    instance_type = 'annotation'

    task = tasks.write_annotation

    views = ['list', 'get', 'add', 'delete']

    embeddable = {'original_data_source': DataSourcesResource,
                  'annotated_data_source': DataSourcesResource}
    filterable = {'annotated_data_source.user': 'user'}

    # Note: We consider an annotation's owner to be the owner of the attached
    #     annotated_data_source, not the owner of the original_data_source.

    list_ensure_conditions = [has_role('admin'), is_user]
    list_ensure_options = {'satisfy': any,
                           'kwargs': {'user': 'annotated_data_source.user'}}

    get_ensure_conditions = [has_role('admin'), owns_annotation]
    get_ensure_options = {'satisfy': any}

    add_ensure_conditions = [has_role('admin'), has_role('annotator'),
                             has_role('trader'), owns_data_source]
    add_ensure_options = {'satisfy': _satisfy_add}
    add_schema = {'data_source': {'type': 'data_source', 'required': True},
                  'name': {'type': 'string', 'maxlength': 200},
                  'global_frequency': {'type': 'boolean'},
                  'sample_frequencies': {'type': 'list',
                                         'maxlength': 30,
                                         'schema': {'type': 'sample'}}}

    delete_ensure_conditions = [has_role('admin'), owns_annotation]
    delete_ensure_options = {'satisfy': any}

    @classmethod
    def serialize(cls, instance, embed=None):
        """
        An annotation is represented as an object with the following fields:

        **uri** (`uri`)
          URI for this resource.

        **task** (`object`)
          Task information, see :ref:`api-tasked-resources`.

        **original_data_source** (`object`)
          :ref:`Link <api-links>` to a :ref:`data source
          <api-resources-data-sources-instances>` resource (embeddable).

        **annotated_data_source** (`object`)
          :ref:`Link <api-links>` to a :ref:`data source
          <api-resources-data-sources-instances>` resource (embeddable).

        .. todo:: Include and document the `global_frequency` and
           `sample_frequencies` fields.
        """
        return super(AnnotationsResource, cls).serialize(instance, embed=embed)

    @classmethod
    def list_view(cls, *args, **kwargs):
        """
        Returns a collection of annotations in the `annotation_collection`
        field.

        .. note:: Requires having the `admin` role or being the user specified
           by the `user` filter.

        **Available filters:**

        - **user** (`uri`)
        """
        return super(AnnotationsResource, cls).list_view(*args, **kwargs)

    @classmethod
    def get_view(cls, *args, **kwargs):
        """
        Returns the annotation representation in the `annotation` field.

        .. note:: Requires having the `admin` role or being the owner of the
           annotation.
        """
        return super(AnnotationsResource, cls).get_view(*args, **kwargs)

    @classmethod
    def add_view(cls, data_source, name=None, global_frequency=True,
                 sample_frequencies=None):
        """
        Adds an annotation resource.

        .. note:: Requires on or more of the following:

           - Having the `admin` role.
           - Having the `annotator` role **and** being the owner of the data
             source specified by the `data_source` field.
           - Having the `trader` role **and** being the owner of the data
             source specified by the `data_source` field.

        **Required request data:**

        - **data_source** (`uri`)

        **Accepted request data:**

        - **name** (`string`)
        - **global_frequency** (`boolean`)
        - **sample_frequencies** (`list` of `uri`)
        """
        # Todo: Check if data source is a VCF file.
        # The `satisfy` keyword argument used here in the `ensure` decorator means
        # that we ensure at least one of:
        # - admin
        # - owns_data_source AND annotator
        # - owns_data_source AND trader
        sample_frequencies = sample_frequencies or []
        name = name or '%s (annotated)' % data_source.name

        for sample in sample_frequencies:
            if not (sample.public or
                    sample.user is g.user or
                    'admin' in g.user.roles):
                # Todo: Meaningful error message.
                abort(400)

        if 'admin' not in g.user.roles and 'annotator' not in g.user.roles:
            # This is a trader, so check if the data source has been imported in
            # an active sample.
            # Todo: Anyone should be able to annotate against the public samples.
            # Todo: This check is bogus when annotating a BED file.
            if not data_source.variations.join(Sample).filter_by(active=True).count():
                raise InvalidDataSource('inactive_data_source', 'Data source '
                    'cannot be annotated unless it is imported in an active sample')

        # For now, we only support VCF->VCF and BED->CSV.
        if data_source.filetype == 'vcf':
            annotated_filetype = 'vcf'
        else:
            annotated_filetype = 'csv'

        annotated_data_source = DataSource(g.user, name, annotated_filetype,
                                           empty=True, gzipped=True)
        db.session.add(annotated_data_source)
        annotation = Annotation(data_source, annotated_data_source,
                                global_frequency=global_frequency,
                                sample_frequencies=sample_frequencies)
        db.session.add(annotation)
        db.session.commit()
        current_app.logger.info('Added data source: %r', annotated_data_source)
        current_app.logger.info('Added annotation: %r', annotation)

        result = tasks.write_annotation.delay(annotation.id)
        annotation.task_uuid = result.task_id
        db.session.commit()
        current_app.logger.info('Called task: write_annotation(%d) %s', annotation.id, result.task_id)
        response = jsonify(annotation=cls.serialize(annotation))
        response.location = cls.instance_uri(annotation)
        return response, 201

    @classmethod
    def edit_view(cls, *args, **kwargs):
        """
        Updates an annotation resource.

        .. note:: Requires having the `admin` role.

        **Accepted request data:**

        - **task** (`object`)
        """
        return super(AnnotationsResource, cls).edit_view(*args, **kwargs)

    @classmethod
    def delete_view(cls, *args, **kwargs):
        """
        Todo: documentation, including how/if we cascade.
        """
        return super(AnnotationsResource, cls).delete_view(*args, **kwargs)
