"""
REST API variants resource.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


import binning
from flask import abort, g, jsonify

from ...models import Observation, Sample, Variation
from ...utils import (calculate_frequency, normalize_region, normalize_variant,
                      ReferenceMismatch)
from ..errors import ValidationError
from ..security import has_role, owns_sample, public_sample, true
from .base import Resource
from .samples import SamplesResource


def _authorize_query(query):
    if query.singleton:
        try:
            sample = query.samples[0]
        except IndexError:
            # This should not really be possible, we already checked the
            # sample exists.
            abort(400)
        if not sample.public:
            if g.user is None:
                abort(401)
            if not (sample.user is g.user or 'admin' in g.user.roles):
                abort(400)
    else:
        if g.user is None:
            abort(401)
        if not ('admin' in g.user.roles or 'annotator' in g.user.roles):
            abort(400)
        if not query.tautology:
            roles = ['admin', 'querier']
            if query.only_group_clauses:
                roles.append('group-querier')
            if not any(role in g.user.roles for role in roles):
                abort(400)


class VariantsResource(Resource):
    """
    Variant resources model genomic variants with their observed frequencies.

    .. note:: The implementation of this resource is still in flux and it is
       therefore not documented.
    """
    instance_name = 'variant'
    instance_type = 'variant'

    views = ['list', 'get', 'add']

    orderable = ['chromosome', 'position']

    default_order = [('chromosome', 'asc'),
                     ('position', 'asc'),
                     ('reference', 'asc'),
                     ('observed', 'asc'),
                     ('id', 'asc')]

    list_ensure_conditions = []
    list_schema = {'region': {'type': 'dict',
                              'schema': {'chromosome': {'type': 'string', 'required': True, 'maxlength': 30},
                                         'begin': {'type': 'integer', 'required': True},
                                         'end': {'type': 'integer', 'required': True}},
                              'required': True},
                   'queries': {'type': 'list',
                               'maxlength': 10,
                               'schema': {'type': 'query'}}}

    get_ensure_conditions = []
    get_schema = {'queries': {'type': 'list',
                              'maxlength': 10,
                              'schema': {'type': 'query'}}}

    add_ensure_conditions = []
    add_schema = {'chromosome': {'type': 'string', 'required': True, 'maxlength': 30},
                  'position': {'type': 'integer', 'required': True},
                  'reference': {'type': 'string', 'maxlength': 200},
                  'observed': {'type': 'string', 'maxlength': 200}}

    key_type = 'string'

    @classmethod
    def instance_key(cls, variant):
        return '%s:%d%s>%s' % variant

    @classmethod
    def serialize(cls, variant, queries=None):
        """
        A variant is represented as an object with the following fields:

        **uri** (`uri`)
          URI for this resource.
        """
        chromosome, position, reference, observed = variant
        queries = queries or []

        serialization = {'uri': cls.instance_uri(variant),
                         'chromosome': chromosome,
                         'position': position,
                         'reference': reference,
                         'observed': observed}

        annotations = {}
        for query in queries:
            coverage, frequency = calculate_frequency(
                chromosome, position, reference, observed,
                samples=query.samples)
            annotations[query.name] = {'coverage': coverage,
                                       'frequency': sum(frequency.values()),
                                       'frequency_het': frequency['heterozygous'],
                                       'frequency_hom': frequency['homozygous']}

        if annotations:
            serialization['annotations'] = annotations

        return serialization

    @classmethod
    def list_view(cls, begin, count, region, queries=None, order=None):
        """
        Returns a collection of variants in the `variant_collection` field.
        """
        queries = queries or []

        # Todo: Document that `begin` and `end` are 1-based and inclusive. Or,
        #     perhaps we should change that to conform to BED track regions.
        try:
            chromosome, begin_position, end_position = normalize_region(
                region['chromosome'], region['begin'], region['end'])
        except ReferenceMismatch as e:
            raise ValidationError(str(e))

        for query in queries:
            if query.singleton:
                query.require_active = False
                query.require_coverage_profile = False
            _authorize_query(query)

        # Set of samples IDs considered by all queries together.
        all_sample_ids = {sample.id
                          for query in queries
                          for sample in query.samples}

        # Set of observations considered by all queries together.
        bins = binning.contained_bins(begin_position - 1, end_position)
        observations = Observation.query.filter(
            Observation.chromosome == chromosome,
            Observation.position >= begin_position,
            Observation.position <= end_position,
            Observation.bin.in_(bins)
        ).join(Variation).join(Sample).filter(
            Sample.id.in_(all_sample_ids)
        ).distinct(
            Observation.chromosome,
            Observation.position,
            Observation.reference,
            Observation.observed
        ).order_by(
            *[getattr(getattr(Observation, f), d)()
                                               for f, d in cls.get_order(order)])

        items = [cls.serialize((o.chromosome, o.position, o.reference, o.observed),
                               queries=queries)
                 for o in observations.limit(count).offset(begin)]
        return (observations.count(),
                jsonify(variant_collection={'uri': cls.collection_uri(),
                                            'items': items}))

    @classmethod
    def get_view(cls, variant, queries=None):
        """
        Returns the variant representation in the `variant` field.
        """
        queries = queries or []

        for query in queries:
            if query.singleton:
                query.require_active = False
                query.require_coverage_profile = False
            _authorize_query(query)

        return jsonify(variant=cls.serialize(variant, queries=queries))

    @classmethod
    def add_view(cls, chromosome, position, reference='', observed=''):
        """
        Adds a variant resource.
        """
        # Todo: Also support HGVS input.
        try:
            variant = normalize_variant(chromosome, position, reference, observed)
        except ReferenceMismatch as e:
            raise ValidationError(str(e))

        response = jsonify(variant=cls.serialize(variant))
        response.location = cls.instance_uri(variant)
        return response, 201
