# -*- coding: utf-8 -*-
"""
REST API views.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from flask import Blueprint, current_app, g, jsonify, request, url_for

from .. import genome
from .. import tasks
from ..models import InvalidDataSource
from .errors import ActivationFailure, ValidationError
from .resources import (AnnotationsResource, CoveragesResource,
                        DataSourcesResource, SamplesResource, UsersResource,
                        VariantsResource, VariationsResource)
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


@api.errorhandler(416)
def error_unsatisfiable_range(error):
    return jsonify(error={
        'code': 'unsatisfiable_range',
        'message': 'Requested range bot satisfiable'}), 416


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
variants_resource = VariantsResource(api, url_prefix='/variants')


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
    # Todo: Genome could be expanded into a separate resource.
    api = {'status':             'ok',
           'version':            API_VERSION,
           'genome':             genome.keys(),
           'authentication':     {'uri': url_for('.authentication')}}
    api.update({resource.instance_name + '_collection':
                    {'uri': resource.collection_uri()}
                for resource in (annotations_resource,
                                 coverages_resource,
                                 data_sources_resource,
                                 samples_resource,
                                 users_resource,
                                 variants_resource,
                                 variations_resource)})
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
