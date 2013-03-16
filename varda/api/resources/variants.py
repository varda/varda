"""
REST API variants resource.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from flask import jsonify

from ...models import Observation
from ...region_binning import all_bins
from ...utils import (calculate_frequency, normalize_region, normalize_variant,
                      ReferenceMismatch)
from ..security import has_role
from .base import Resource


class VariantsResource(Resource):
    """
    A variant is represented as an object with the following fields:

    **Note:** This resource is subject to change and therefore not documented
        yet.
    """
    instance_name = 'variant'
    instance_type = 'variant'

    views = ['list', 'get', 'add']

    list_ensure_conditions = [has_role('admin'), has_role('annotator')]
    list_ensure_options = {'satisfy': any}
    list_schema = {'region': {'type': 'dict',
                              'schema': {'chromosome': {'type': 'string', 'required': True, 'maxlength': 30},
                                         'begin': {'type': 'integer', 'required': True},
                                         'end': {'type': 'integer', 'required': True}},
                              'required': True},
                   'global_frequency': {'type': 'boolean'},
                   'sample_frequency': {'type': 'list',
                                        'maxlength': 20,
                                        'schema': {'type': 'sample'}},
                   'exclude': {'type': 'list',
                               'maxlength': 30,
                               'schema': {'type': 'sample'}}}

    get_ensure_conditions = [has_role('admin'), has_role('annotator')]
    get_ensure_options = {'satisfy': any}
    get_schema = {'global_frequency': {'type': 'boolean'},
                  'sample_frequency': {'type': 'list',
                                       'maxlength': 20,
                                       'schema': {'type': 'sample'}},
                  'exclude': {'type': 'list',
                              'maxlength': 20,
                              'schema': {'type': 'sample'}}}

    add_ensure_conditions = []
    add_schema = {'chromosome': {'type': 'string', 'required': True, 'maxlength': 30},
                  'position': {'type': 'integer', 'required': True},
                  'reference': {'type': 'string', 'maxlength': 200},
                  'observed': {'type': 'string', 'maxlength': 200}}

    key_type = 'string'

    @classmethod
    def list_view(cls, begin, count, region, global_frequency=True,
                  sample_frequency=None, exclude=None):
        """
        Get a collection of variants.
        """
        sample_frequency = sample_frequency or []
        exclude = exclude or []

        for sample in sample_frequency:
            if not (sample.public or
                    sample.user is g.user or
                    'admin' in g.user.roles):
                # Todo: Meaningful error message.
                abort(400)

        # Todo: Note that we mean start, stop to be 1-based, inclusive, but we
        #     haven't checked if we actually treat it that way.
        try:
            chromosome, begin_position, end_position = normalize_region(
                region['chromosome'], region['begin'], region['end'])
        except ReferenceMismatch as e:
            raise ValidationError(str(e))

        # Todo: Only report variants that have positive frequency in the
        #     calculation for this view?
        bins = all_bins(begin_position, end_position)
        observations = Observation.query.filter(
            Observation.chromosome == chromosome,
            Observation.position >= begin_position,
            Observation.position <= end_position,
            Observation.bin.in_(bins))

        return (observations.count(),
                jsonify(variants=[cls.serialize((o.chromosome, o.position, o.reference, o.observed),
                                                global_frequency=global_frequency,
                                                sample_frequency=sample_frequency,
                                                exclude=exclude)
                                  for o in observations.limit(count).offset(begin)]))

    @classmethod
    def get_view(cls, variant, global_frequency=True, sample_frequency=None,
                 exclude=None):
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
        sample_frequency = sample_frequency or []
        exclude = exclude or []

        for sample in sample_frequency:
            if not (sample.public or
                    sample.user is g.user or
                    'admin' in g.user.roles):
                # Todo: Meaningful error message.
                abort(400)

        return jsonify(variant=cls.serialize(variant,
                                             global_frequency=global_frequency,
                                             sample_frequency=sample_frequency,
                                             exclude=exclude))

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
        uri = cls.instance_uri(variant)
        response = jsonify({'variant_uri': uri})
        response.location = uri
        return response, 201

    @classmethod
    def instance_key(cls, variant):
        return '%s:%d%s>%s' % variant

    @classmethod
    def serialize(cls, variant, global_frequency=True, sample_frequency=None,
                  exclude=None):
        sample_frequency = sample_frequency or []
        exclude = exclude or []

        chromosome, position, reference, observed = variant

        global_frequency_result, sample_frequency_result = calculate_frequency(
            chromosome, position, reference, observed, global_frequency,
            sample_frequency, exclude)

        return {'uri': cls.instance_uri(variant),
                'chromosome': chromosome,
                'position': position,
                'reference': reference,
                'observed': observed,
                'global_frequency': global_frequency_result,
                'sample_frequency': sample_frequency_result}
