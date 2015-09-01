"""
REST API annotations model resource.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


import re

from flask import abort, current_app, g, jsonify, url_for

from ... import db
from ...models import (Annotation, DataSource, InvalidDataSource, Sample,
                       Variation)
from ... import expressions, tasks
from ..security import has_role, is_user, owns_annotation, owns_data_source
from .base import TaskedResource
from .data_sources import DataSourcesResource


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

    add_ensure_conditions = [has_role('admin'), owns_data_source]
    add_ensure_options = {'satisfy': any}
    add_schema = {'data_source': {'type': 'data_source', 'required': True},
                  'name': {'type': 'string', 'maxlength': 200},
                  'queries': {'type': 'list',
                              'maxlength': 10,
                              'schema': {'type': 'query'}}}

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

        .. todo:: Include and document the associated queries.
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
    def add_view(cls, data_source, name=None, queries=None):
        """
        Adds an annotation resource.

        .. note:: Requires having the `admin` role or being the owner of the
           data source specified by the `data_source` field.

           Queries may have additional requirements depending on their
           expression:

           1. Query expressions of the form ``sample:<uri>`` require one of
              the following:

              - Having the `admin` role.
              - Owning the sample specified by ``<uri>``.
              - The sample specified by ``<uri>`` being public.

           2. Query expressions of the form ``*`` require having the `admin`,
              `annotator`, or `trader` role, where the `trader` role
              additionally requires that `data_source` has been imported as
              variation in an active sample.

           3. Query expressions containing only group clauses require the same
              as those of the form ``*``, where the `annotator` and `trader`
              roles additionally require having the `group-querier` role.

           4. Other query expressions require the same as those containing only
              group clauses, where the `annotator` and `trader` roles require
              having the `querier` role instead of the `group-querier` role.

        **Required request data:**

        - **data_source** (`uri`)

        **Accepted request data:**

        - **name** (`string`)
        - **queries** (`list` of `object`)

        Every object in the `queries` list defines a
        :ref:`query <api-queries>`; a set of samples over which observation
        frequencies are annotated. When annotating a VCF data source, any
        samples having this data source as variation are excluded.
        """
        queries = queries or []
        name = name or '%s (annotated)' % data_source.name

        # Samples that have this data source as an imported VCF file.
        data_source_samples = Sample.query.join(Variation).filter_by(
            data_source_id=data_source.id).all()

        # Todo: Meaningful error messages instead of abort(400).
        for query in queries:
            if query.singleton:
                query.require_active = False
                query.require_coverage_profile = False

                try:
                    sample = query.samples[0]
                except IndexError:
                    # This should not really be possible, we already checked
                    # the sample exists.
                    abort(400)

                if not (sample.public or
                        sample.user is g.user or
                        'admin' in g.user.roles):
                    abort(400)

            else:
                if not ('admin' in g.user.roles or 'annotator' in g.user.roles):
                    if 'trader' in g.user.roles:
                        if not data_source.variations.join(Sample).filter_by(active=True).count():
                            raise InvalidDataSource(
                                'inactive_data_source', 'Data source cannot '
                                'be annotated unless it is imported in an '
                                'active sample')
                    else:
                        abort(400)

                if not query.tautology:
                    roles = ['admin', 'querier']
                    if query.only_group_clauses:
                        roles.append('group-querier')

                    if not any(role in g.user.roles for role in roles):
                        abort(400)

            # If we are annotating a VCF file that is part of an imported
            # sample, we should exclude that sample.
            for sample in data_source_samples:
                query.expression = expressions.make_conjunction(
                    expressions.parse('not sample:%d' % sample.id),
                    query.expression)

        # For now, we only support VCF->VCF and BED->CSV.
        if data_source.filetype == 'vcf':
            annotated_filetype = 'vcf'
        else:
            annotated_filetype = 'csv'

        annotated_data_source = DataSource(g.user, name, annotated_filetype,
                                           empty=True, gzipped=True)
        db.session.add(annotated_data_source)
        annotation = Annotation(data_source, annotated_data_source,
                                queries=queries)
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
