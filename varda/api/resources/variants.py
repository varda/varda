"""
REST API variants resource.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from __future__ import division

from flask import jsonify, url_for

from ...models import Coverage, Observation, Region, Sample, Variation
from ...region_binning import all_bins
from ...utils import normalize_region, normalize_variant, ReferenceMismatch
from ..security import has_role
from .base import Resource


class VariantsResource(Resource):
    """
    A variant is represented as an object with the following fields:

    .. todo: `List` and `get` give different information, I think this should
        be fixed before writing documentation.
    """
    instance_name = 'variant'
    instance_type = 'variant'

    views = ['list', 'get', 'add']

    list_ensure_conditions = [has_role('admin'), has_role('annotator')]
    list_ensure_options = {'satisfy': any}
    list_schema = {'region': {'type': 'dict',
                              'schema': {'chromosome': {'type': 'string', 'required': True},
                                         'begin': {'type': 'integer', 'required': True},
                                         'end': {'type': 'integer', 'required': True}},
                              'required': True}}

    get_ensure_conditions = [has_role('admin'), has_role('annotator')]
    get_ensure_options = {'satisfy': any}

    add_ensure_conditions = []
    add_schema = {'chromosome': {'type': 'string', 'required': True},
                  'position': {'type': 'integer', 'required': True},
                  'reference': {'type': 'string'},
                  'observed': {'type': 'string'}}

    key_type = 'string'

    @classmethod
    def list_view(cls, begin, count, region):
        """
        Get a collection of variants.
        """
        # Todo: Note that we mean start, stop to be 1-based, inclusive, but we
        #     haven't checked if we actually treat it that way.
        try:
            chromosome, begin_position, end_position = normalize_region(
                region['chromosome'], region['begin'], region['end'])
        except ReferenceMismatch as e:
            raise ValidationError(str(e))

        bins = all_bins(begin_position, end_position)
        observations = Observation.query.filter(
            Observation.chromosome == chromosome,
            Observation.position >= begin_position,
            Observation.position <= end_position,
            Observation.bin.in_(bins))

        def serialize(o):
            return {'uri': url_for('.variant_get', variant='%s:%d%s>%s' % (o.chromosome, o.position, o.reference, o.observed)),
                    'hgvs': '%s:g.%d%s>%s' % (o.chromosome, o.position, o.reference, o.observed),
                    'chromosome': o.chromosome,
                    'position': o.position,
                    'reference': o.reference,
                    'observed': o.observed}

        return (observations.count(),
                jsonify(variants=[serialize(o) for o in
                                  observations.limit(count).offset(begin)]))

    @classmethod
    def get_view(cls, variant):
        """
        Get frequency details for a variant.

        Requires the `admin` or `annotator` role.

        :statuscode 200: Respond with an object defined below as `variant`.

        The response object has the following fields:

        * **uri** (`string`) - URI for this variant.
        * **chromosome** (`string`) - Chromosome name.
        * **position** (`integer`) - Start position of the variant.
        * **reference** (`string`) - Reference sequence.
        * **observed** (`string`) - Observed sequence.
        * **hgvs** (`string`) - HGVS description.
        * **frequency** (`float`) - Frequency in database samples.
        """
        chromosome, position, reference, observed = variant

        # Todo: Abstract this away for reuse in tasks and here.

        end_position = position + max(1, len(reference)) - 1
        bins = all_bins(position, end_position)

        exclude_sample_ids = []

        observations = Observation.query.filter_by(
            chromosome=chromosome,
            position=position,
            reference=reference,
            observed=observed).join(Variation).filter(
                ~Variation.sample_id.in_(exclude_sample_ids)).join(Sample).filter_by(
                    active=True, coverage_profile=True).count()

        coverage = Region.query.join(Coverage).filter(
            Region.chromosome == chromosome,
            Region.begin <= position,
            Region.end >= end_position,
            Region.bin.in_(bins),
            ~Coverage.sample_id.in_(exclude_sample_ids)).join(Sample).filter_by(active=True).count()

        try:
            frequency = observations / coverage
        except ZeroDivisionError:
            frequency = 0

        # Todo: HGVS description is of course not really HGVS.
        return jsonify(variant={'uri': url_for('.variant_get', variant=variant),
                                'hgvs': '%s:g.%d%s>%s' % variant,
                                'chromosome': chromosome,
                                'position': position,
                                'reference': reference,
                                'observed': observed,
                                'frequency': frequency})

    @classmethod
    def add_view(cls, chromosome, position, reference='', observed=''):
        """
        Create a variant.
        """
        # Todo: Also support HGVS input.
        try:
            variant = normalize_variant(chromosome, position, reference, observed)
        except ReferenceMismatch as e:
            raise ValidationError(str(e))
        uri = url_for('.variant_get', variant='%s:%d%s>%s' % variant)
        response = jsonify({'variant_uri': uri})
        response.location = uri
        return response, 201
