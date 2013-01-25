"""
REST API views.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from __future__ import division

from flask import Blueprint, current_app, g, jsonify, request, url_for

from .. import genome
from .. import tasks
from ..models import (Coverage, InvalidDataSource, Observation, Region,
                      Sample, Variation)
from ..region_binning import all_bins
from ..utils import normalize_variant, ReferenceMismatch
from .data import data
from .errors import ActivationFailure, ValidationError
from .resources import (AnnotationsResource, CoveragesResource,
                        DataSourcesResource, SamplesResource, UsersResource,
                        VariationsResource)
from .security import ensure, has_role, require_user
from .utils import user_by_login


API_VERSION = 1


api = Blueprint('api', 'api')


@api.before_request
def register_user():
    """
    Make sure we add a :class:`.User` instance to the global objects if we
    have authentication.
    """
    auth = request.authorization
    g.user = user_by_login(auth.username, auth.password) if auth else None
    if auth and g.user is None:
        current_app.logger.warning('Unsuccessful authentication with '
                                   'username "%s"', auth.username)


@api.errorhandler(400)
def error_bad_request(error):
    return jsonify(error={
        'code': 'bad_request',
        'message': 'The request could not be understood due to malformed syntax'}), 400


@api.errorhandler(401)
def error_unauthorized(error):
    return jsonify(error={
        'code': 'unauthorized',
        'message': 'The request requires user authentication'}), 401


@api.errorhandler(403)
def error_forbidden(error):
    return jsonify(error={
        'code': 'forbidden',
        'message': 'Not allowed to make this request'}), 403


@api.errorhandler(404)
@api.app_errorhandler(404)
def error_not_found(error):
    return jsonify(error={
        'code': 'not_found',
        'message': 'The requested entity could not be found'}), 404


@api.errorhandler(413)
def error_entity_too_large(error):
    return jsonify(error={
        'code': 'entity_too_large',
        'message': 'The request entity is too large'}), 413


@api.errorhandler(501)
def error_not_implemented(error):
    return jsonify(error={
        'code': 'not_implemented',
        'message': 'The functionality required to fulfill the request is currently not implemented'}), 501


@api.errorhandler(tasks.TaskError)
def error_task_error(error):
    return jsonify(error={'code': error.code,
                          'message': error.message}), 500


@api.errorhandler(ActivationFailure)
@api.errorhandler(InvalidDataSource)
def error_(error):
    return jsonify(error={'code': error.code,
                          'message': error.message}), 400


@api.errorhandler(ValidationError)
def error_(error):
    return jsonify(error={'code': 'bad_request',
                          'message': error.message}), 400


users_resource = UsersResource(api, url_prefix='/users')
samples_resource = SamplesResource(api, url_prefix='/samples')
variations_resource = VariationsResource(api, url_prefix='/variations')
coverages_resource = CoveragesResource(api, url_prefix='/coverages')
data_sources_resource = DataSourcesResource(api, url_prefix='/data_sources')
annotations_resource = AnnotationsResource(api, url_prefix='/annotations')


@api.route('/')
def apiroot():
    """
    Varda server status information.

    :statuscode 200: Respond with an object as defined below.

    The response object has the following fields:

    * **status** (`string`) - Currently always ``ok``, but future versions of
      the API might add other values (e.g. ``maintanance``).
    * **version** (`integer`) - API version.
    * **genome** (`list of string`) - Reference genome chromosome names.
    * **authentication_uri** (`string`) - URI for the :ref:`authentication
      state <api_misc>`.
    * **users_uri** (`string`) - URI for the :ref:`registered users resource <api_users>`.
    * **samples_uri** (`string`) - URI for the :ref:`samples resource <api_samples>`.
    * **data_sources_uri** (`string`) - URI for the :ref:`data sources
      resource <api_data_sources>`.
    """
    api = {'status':             'ok',
           'version':            API_VERSION,
           'genome':             genome.keys(),
           'authentication_uri': url_for('.authentication'),
           'users_uri':          url_for('.user_list'),
           'samples_uri':        url_for('.sample_list'),
           'variations_uri':     url_for('.variation_list'),
           'coverages_uri':      url_for('.coverage_list'),
           'data_sources_uri':   url_for('.data_source_list'),
           'annotations_uri':    url_for('.annotation_list'),
           'variants_uri':       url_for('.variant_list')}
    return jsonify(api)


@api.route('/authentication')
def authentication():
    """
    Authentication state (for this very request).

    :statuscode 200: Respond with the authentication state as `authenticated`
        and, if true, a :ref:`user <api_users>` object as `user`.

    Example request:

    .. sourcecode:: http

        GET /authentication HTTP/1.1

    Example response:

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
          "authenticated": true,
          "user":
            {
              "uri": "/users/1",
              "name": "Frederick Sanger",
              "login": "fred",
              "roles": ["admin"],
              "added": "2012-11-23T10:55:12.776706"
            }
        }
    """
    authentication = {'authenticated': False}
    if g.user is not None:
        authentication.update(authenticated=True,
                              user=users_resource.serialize(g.user))
    return jsonify(authentication)


@api.route('/variants')
def variant_list():
    abort(501)


@api.route('/variants/<variant>')
@require_user
@data(variant={'type': 'variant'})
@ensure(has_role('admin'), has_role('annotator'), satisfy=any)
def variant_get(variant):
    """
    Get frequency details for a variant.

    Requires the `admin` or `annotator` role.

    :statuscode 200: Respond with an object defined below as `variant`.

    The response object has the following fields:

    * **chromosome** (`string`) - Chromosome name.
    * **position** (`integer`) - Start position of the variant.
    * **reference** (`string`) - Reference sequence.
    * **observed** (`string`) - Observed sequence.
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

    return jsonify(variant={'chromosome': chromosome,
                            'position': position,
                            'reference': reference,
                            'observed': observed,
                            'frequency': frequency})


@api.route('/variants', methods=['POST'])
@require_user
@data(chromosome={'type': 'string', 'required': True},
      position={'type': 'integer', 'required': True},
      reference={'type': 'string'},
      observed={'type': 'string'})
def variant_add(chromosome, position, reference='', observed=''):
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
