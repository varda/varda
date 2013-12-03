# -*- coding: utf-8 -*-
"""
REST API views.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from flask import Blueprint, current_app, g, jsonify, request, url_for
import semantic_version

from .. import genome
from .. import tasks
from ..models import InvalidDataSource
from ..utils import chromosome_compare_key
from .errors import (AcceptError, ActivationFailure, BasicAuthRequiredError,
                     IntegrityError, ValidationError)
from .resources import (AnnotationsResource, CoveragesResource,
                        DataSourcesResource, SamplesResource, TokensResource,
                        UsersResource, VariantsResource, VariationsResource)
from .utils import user_by_login, user_by_token


API_VERSION = semantic_version.Version('1.0.0')


api = Blueprint('api', 'api')


@api.before_request
def check_accept_api_version():
    """
    Clients can ask for specific versions of our API with a `Semantic
    Versioning <http://semver.org/>`_ specification in the `Accept-Version`
    header. If no `Accept-Version` header is present, a value of ``>=0.1``
    (matching any current or future version) is assumed.

    In the future, we could use this to make changes in a backwards compatible
    way. One extreme would be to route to different installations of Varda,
    based on the `Accept-Version` header. Smaller changes could be implemented
    by supporting different API versions on specific endpoints.

    For now, we have one static version for the entire API and just check if
    it matches `Accept-Version`, so no negotiation on version really. Anyway,
    it's important that the mechanism is in place such that it can be used by
    clients, in anticipation of future requirements.
    """
    # Todo: Should return error if Accept-Version is set but not a valid
    #     version specification (currently ignore silently).
    accept = request.headers.get('Accept-Version', type=semantic_version.Spec)
    if accept and not API_VERSION in accept:
        raise AcceptError('no_acceptable_version', 'No acceptable version of '
                          'the API is available (only %s)' % API_VERSION)


@api.after_request
def add_api_version(response):
    """
    Add a header `Api-Version` with the API version. If in the future we start
    doing version negotiation, the chosen version could be stored on the `g`
    global and read from there.
    """
    response.headers.add('Api-Version', str(API_VERSION))
    return response


@api.before_request
def register_user():
    """
    Make sure we add a :class:`.User` instance to the global objects if we
    have authentication.

    Authentication can be achieved either by HTTP Basic Authentication using
    login and password, or by token authentication.
    """
    user = None
    auth_method = None

    auth = request.authorization
    if auth:
        user = user_by_login(auth.username, auth.password)
        if user is None:
            current_app.logger.warning('Unsuccessful authentication with '
                                       'username "%s"', auth.username)
        else:
            auth_method = 'basic-auth'
    else:
        auth = request.headers.get('Authorization', '').split()
        if len(auth) == 2 and auth[0] == 'Token':
            user = user_by_token(auth[1])
            if user is None:
                current_app.logger.warning('Unsuccessful authentication with '
                                           'token "%s"', auth[1])
            else:
                auth_method = 'token'

    g.user = user
    g.auth_method = auth_method


@api.errorhandler(400)
def error_bad_request(error):
    return jsonify(error={
        'code': 'bad_request',
        'message': 'The request could not be understood due to malformed syntax'}), 400


@api.errorhandler(401)
def error_unauthorized(error):
    # Todo: To quote the HTTP specification: "The response MUST include a
    #     WWW-Authenticate header field (section 14.47) containing a challenge
    #     applicable to the requested resource."
    #     We don't do that at the moment. A browser will automatically come up
    #     with a authentication popup, and if this is also the case for Ajax
    #     requests it breaks Aulë (it has its own authentication form). Need
    #     to test this accross browsers.
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


@api.errorhandler(416)
def error_unsatisfiable_range(error):
    return jsonify(error={
        'code': 'unsatisfiable_range',
        'message': 'Requested range not satisfiable'}), 416


# Note: It is currently not possible to register a 500 internal server error
#     on a per-blueprint level in Flask, so we have no other choice than to
#     register it on the application. The downside in our case is small, since
#     we only serve Aulë static files (if configured) besides our API. It is
#     important for clients that they get 500 error codes encoded as JSON.
@api.app_errorhandler(500)
def error_internal(error):
    return jsonify(error={
        'code': 'internal_server_error',
        'message': 'The server encountered an unexpected condition which prevented it from fulfilling the request'}), 500


@api.errorhandler(501)
def error_not_implemented(error):
    return jsonify(error={
        'code': 'not_implemented',
        'message': 'The functionality required to fulfill the request is currently not implemented'}), 501


@api.errorhandler(tasks.TaskError)
def error_task_error(error):
    return jsonify(error={'code': error.code,
                          'message': error.message}), 500


# Tody: This probably shouldn't be 400. Perhaps 409, like IntegrityError?
@api.errorhandler(ActivationFailure)
@api.errorhandler(InvalidDataSource)
def error_(error):
    return jsonify(error={'code': error.code,
                          'message': error.message}), 400


@api.errorhandler(ValidationError)
def error_(error):
    return jsonify(error={'code': 'bad_request',
                          'message': error.message}), 400


@api.errorhandler(BasicAuthRequiredError)
def error_(error):
    return jsonify(error={'code': 'basic_auth_required',
                          'message': 'The request requires login/password authentication'}), 401


@api.errorhandler(AcceptError)
def error_(error):
    return jsonify(error={'code': error.code,
                          'message': error.message}), 406


@api.errorhandler(IntegrityError)
def error_(error):
    return jsonify(error={'code': 'integrity_conflict',
                          'message': error.message}), 409


users_resource = UsersResource(api, url_prefix='/users')
tokens_resource = TokensResource(api, url_prefix='/tokens')
samples_resource = SamplesResource(api, url_prefix='/samples')
variations_resource = VariationsResource(api, url_prefix='/variations')
coverages_resource = CoveragesResource(api, url_prefix='/coverages')
data_sources_resource = DataSourcesResource(api, url_prefix='/data_sources')
annotations_resource = AnnotationsResource(api, url_prefix='/annotations')
variants_resource = VariantsResource(api, url_prefix='/variants')


@api.route('/')
def root_get():
    """
    Returns the resource representation in the `root` field.

    **Example request**:

    .. sourcecode:: http

       GET / HTTP/1.1

    **Example response**:

    .. sourcecode:: http

       HTTP/1.1 200 OK
       Content-Type: application/json

       {
         "root": {
           "uri": "/",
           "api_version": "0.3.0",
           "status": "ok",
           "authentication": {
             "uri": "/authentication"
           },
           "genome": {
             "uri": "/genome"
           },
           "annotation_collection": {
             "uri": "/annotations/"
           },
           "coverage_collection": {
             "uri": "/coverages/"
           },
           "data_source_collection": {
             "uri": "/data_sources/"
           },
           "sample_collection": {
             "uri": "/samples/"
           },
           "token_collection": {
             "uri": "/tokens/"
           },
           "user_collection": {
             "uri": "/users/"
           },
           "variant_collection": {
             "uri": "/variants/"
           },
           "variation_collection": {
             "uri": "/variations/"
           }
         }
       }
    """
    return jsonify(root=root_serialize())


def root_serialize():
    """
    The root resource representation has the following fields:

    **uri** (`uri`)
      URI for this resource.

    **status** (`string`)
      Currently always ``ok``, but future versions of the API
      might add other values (e.g. ``maintanance``).

    **api_version** (`string`)
      API version (see :ref:`api-versioning`).

    **authentication** (`object`)
      :ref:`Link <api-links>` to the :ref:`authentication
      <api-resources-authentication>` resource.

    **genome** (`object`)
      :ref:`Link <api-links>` to the :ref:`genome <api-resources-genome>`
      resource.

    **annotation_collection** (`object`)
      :ref:`Link <api-links>` to the :ref:`annotation collection
      <api-resources-annotations-collection>` resource.

    **coverage_collection** (`object`)
      :ref:`Link <api-links>` to the :ref:`coverage collection
      <api-resources-coverages-collection>` resource.

    **data_source_collection** (`object`)
      :ref:`Link <api-links>` to the :ref:`data_source collection
      <api-resources-data-sources-collection>` resource.

    **sample_collection** (`object`)
      :ref:`Link <api-links>` to the :ref:`sample collection
      <api-resources-samples-collection>` resource.

    **token_collection** (`object`)
      :ref:`Link <api-links>` to the :ref:`token collection
      <api-resources-tokens-collection>` resource.

    **user_collection** (`object`)
      :ref:`Link <api-links>` to the :ref:`user collection
      <api-resources-users-collection>` resource.

    **variant_collection** (`object`)
      :ref:`Link <api-links>` to the :ref:`variant collection
      <api-resources-variants-collection>` resource.

    **variation_collection** (`object`)
      :ref:`Link <api-links>` to the :ref:`variation collection
      <api-resources-variations-collection>` resource.
    """
    # Todo: Option to embed genome and/or authentication resources.
    api = {'uri':                url_for('.root_get'),
           'status':             'ok',
           'api_version':        str(API_VERSION),
           'authentication':     {'uri': url_for('.authentication_get')},
           'genome':             {'uri': url_for('.genome_get')}}
    api.update({resource.instance_name + '_collection':
                    {'uri': resource.collection_uri()}
                for resource in (annotations_resource,
                                 coverages_resource,
                                 data_sources_resource,
                                 samples_resource,
                                 tokens_resource,
                                 users_resource,
                                 variants_resource,
                                 variations_resource)})
    return api


@api.route('/authentication')
def authentication_get():
    """
    Returns the resource representation in the `authentication` field.

    **Example request**:

    .. sourcecode:: http

       GET /authentication HTTP/1.1

    **Example response**:

    .. sourcecode:: http

       HTTP/1.1 200 OK
       Content-Type: application/json

       {
         "authentication": {
           "uri": "/authentication",
           "authenticated": true,
           "user": {
             "uri": "/users/1"
             "added": "2012-11-30T20:14:27.954255",
             "email": null,
             "login": "admin",
             "name": "Admin User",
             "roles": [
               "admin"
             ],
           }
         }
       }
    """
    return jsonify(authentication=authentication_serialize())


def authentication_serialize():
    """
    The authentication resource representation has the following fields:

    **uri** (`uri`)
      URI for this resource.

    **authenticated** (`boolean`)
      Whether or not the request is authenticated.

    **user** (`object`)
      :ref:`Link <api-links>` to a :ref:`user <api-resources-users-instances>`
      resource if the request is authenticated, `null` otherwise.
    """
    authentication = {'uri':           url_for('.authentication_get'),
                      'authenticated': False,
                      'user':          None}
    if g.user is not None:
        authentication.update(authenticated=True,
                              user=users_resource.serialize(g.user))
    return authentication


@api.route('/genome')
def genome_get():
    """
    Returns the resource representation in the `genome` field.
    """
    if not genome:
        abort(404)
    return jsonify(genome=genome__serialize())


def genome_serialize():
    """
    The genome resource representation has the following fields:

    **uri** (`uri`)
      URI for this resource.

    **chromosomes** (`list` of `string`)
      List of chromosome names.
    """
    # Todo: Also configure a genome name (assembly) to report here.
    return {'uri':         url_for('.genome_get'),
            'chromosomes': sorted(genome.keys(), key=chromosome_compare_key)}
