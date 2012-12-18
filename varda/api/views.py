"""
REST API views.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


import os
import re
import uuid

import celery.exceptions
from flask import (abort, Blueprint, current_app, g, jsonify, redirect,
                   request, send_from_directory, url_for)

from .. import db, genome
from ..models import (Annotation, Coverage, DataSource, DATA_SOURCE_FILETYPES,
                      InvalidDataSource, Observation, Sample, User,
                      USER_ROLES, Variation)
from .. import tasks
from .data import data, data_is_true, data_is_user
from .errors import ActivationFailure, ValidationError
from .security import (ensure, has_login, has_role, owns_data_source,
                       owns_sample, require_user)
from .serialize import serialize
from .utils import collection, user_by_login


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
    return jsonify(error=serialize(error)), 500


@api.errorhandler(ActivationFailure)
@api.errorhandler(InvalidDataSource)
@api.errorhandler(ValidationError)
def error_(error):
    return jsonify(error=serialize(error)), 400


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
    * **authentication_uri** (`string`) - URI for the :ref:`authentication state <api_misc>`.
    * **users_uri** (`string`) - URI for the :ref:`registered users resource <api_users>`.
    * **samples_uri** (`string`) - URI for the :ref:`samples resource <api_samples>`.
    * **data_sources_uri** (`string`) - URI for the :ref:`data sources resource <api_data_sources>`.
    """
    api = {'status':             'ok',
           'version':            API_VERSION,
           'genome':             genome.keys(),
           'authentication_uri': url_for('.authentication'),
           'users_uri':          url_for('.users_list'),
           'samples_uri':        url_for('.samples_list'),
           'data_sources_uri':   url_for('.data_sources_list')}
    return jsonify(api=api)


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
              "uri": "/users/fred",
              "name": "Frederick Sanger",
              "login": "fred",
              "roles": ["admin"],
              "added": "2012-11-23T10:55:12.776706"
            }
        }
    """
    authentication = {'authenticated': False}
    if g.user is not None:
        authentication.update(authenticated=True, user=serialize(g.user))
    return jsonify(authentication=authentication)


@api.route('/users', methods=['GET'])
@collection
@require_user
@ensure(has_role('admin'))
def users_list(begin, count):
    """
    Collection of registered users.

    .. todo:: Document what it means to be a collection of resources.

    Requires the `admin` role.

    :statuscode 200: Respond with a list of :ref:`user <api_users>` objects
        as `users`.

    Example request:

    .. sourcecode:: http

        GET /users HTTP/1.1

    Example response:

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
          "users":
            [
              {
                "uri": "/users/fred",
                "name": "Frederick Sanger",
                "login": "fred",
                "roles": ["admin"],
                "added": "2012-11-23T10:55:12.776706"
              },
              {
                "uri": "/users/walter",
                "name": "Walter Gilbert",
                "login": "walter",
                "roles": ["importer", "annotator"],
                "added": "2012-11-23T10:55:12.776706"
              }
            ]
        }
    """
    users = User.query
    return (users.count(),
            jsonify(users=[serialize(u) for u in
                           users.limit(count).offset(begin)]))


@api.route('/users/<login>', methods=['GET'])
@require_user
@ensure(has_role('admin'), has_login, satisfy=any)
def users_get(login):
    """
    Details for user identified by `login`.

    Requires the `admin` role or being the requested user.

    :statuscode 200: Respond with a :ref:`user <api_users>` object as `user`.

    Example request:

    .. sourcecode:: http

        GET /users/fred HTTP/1.1

    Example response:

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
          "user":
            {
              "uri": "/users/fred",
              "name": "Frederick Sanger",
              "login": "fred",
              "roles": ["admin"],
              "added": "2012-11-23T10:55:12.776706"
            }
        }
    """
    user = User.query.filter_by(login=login).first()
    if user is None:
        abort(404)
    return jsonify(user=serialize(user))


@api.route('/users', methods=['POST'])
@data(login={'type': 'string', 'minlength': 3, 'maxlength': 40, 'safe': True,
             'required': True},
      name={'type': 'string'},
      password={'type': 'string', 'required': True},
      roles={'type': 'list', 'allowed': USER_ROLES})
@require_user
@ensure(has_role('admin'))
def users_add(data):
    """
    Create a user.

    Requires the `admin` role.

    :arg login: User login used for identification.
    :type login: string
    :arg name: Human readable name (default: `login`).
    :type name: string
    :arg password: Password.
    :type password: string
    :arg roles: Roles to assign.
    :type roles: list of string
    :statuscode 201: Respond with a URI for the created user as `user`.

    Example request:

    .. sourcecode:: http

        POST /users HTTP/1.1
        Content-Type: application/json

        {
          "name": "Paul Berg",
          "login": "paul",
          "password": "dna",
          "roles": ["importer"]
        }

    Example response:

    .. sourcecode:: http

        HTTP/1.1 201 CREATED
        Location: https://example.com/users/fred
        Content-Type: application/json

        {
          "user_uri": "/users/paul"
        }
    """
    if User.query.filter_by(login=data['login']).first() is not None:
        raise ValidationError('User login is not unique')
    user = User(data.get('name', data['login']),
                data['login'],
                data['password'],
                data.get('roles', []))
    db.session.add(user)
    db.session.commit()
    current_app.logger.info('Added user: %r', user)
    uri = url_for('.users_get', login=user.login)
    response = jsonify(user_uri=uri)
    response.location = uri
    return response, 201


@api.route('/samples', methods=['GET'])
@collection
@data(public={'type': 'boolean'},
      user={'type': 'user'})
@ensure(has_role('admin'), data_is_true('public'), data_is_user('user'),
        satisfy=any)
def samples_list(begin, count, data):
    """
    Collection of samples.

    Requires one of the following:
     * the `admin` role
     * being the user specified in the `user` argument
     * the `public` argument set to ``True``

    :arg public: If set to ``True`` or ``False``, restrict the collection to
        public or non-public samples, respectively.
    :type public: boolean
    :arg user: If set to the URI for a user, restrict the collection to
        samples owned by this user.
    :type user: string
    :statuscode 200: Respond with a list of :ref:`sample <api_samples>`
        objects as `samples`.

    Example request:

    .. sourcecode:: http

        GET /samples?public=true HTTP/1.1

    Example response:

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
          "samples":
            [
              {
                "uri": "/samples/3",
                "user_uri": "/users/fred",
                "variations_uri": "/samples/3/variations",
                "coverages_uri": "/samples/3/coverages",
                "name": "1KG phase 1 release",
                "pool_size": 1092,
                "public": true,
                "added": "2012-11-23T10:55:12.776706"
              },
              {
                "uri": "/samples/4",
                "user_uri": "/users/fred",
                "variations_uri": "/samples/4/variations",
                "coverages_uri": "/samples/4/coverages",
                "name": "GoNL SNP release 4",
                "pool_size": 769,
                "public": true,
                "added": "2012-11-23T10:55:13.776706"
              }
            ]
        }
    """
    samples = Sample.query.filter_by(**data)
    return (samples.count(),
            jsonify(samples=[serialize(s) for s in
                             samples.limit(count).offset(begin)]))


@api.route('/samples/<int:sample_id>', methods=['GET'])
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def samples_get(sample_id):
    """
    Details for sample.

    Requires the `admin` role or being the owner of the requested sample.

    :statuscode 200: Respond with a :ref:`sample <api_samples>` object as
        `sample`.

    Example request:

    .. sourcecode:: http

        GET /samples/3 HTTP/1.1

    Example response:

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
          "sample":
            {
              "uri": "/samples/3",
              "user_uri": "/users/fred",
              "variations_uri": "/samples/3/variations",
              "coverages_uri": "/samples/3/coverages",
              "name": "1KG phase 1 release",
              "pool_size": 1092,
              "public": true,
              "added": "2012-11-23T10:55:12.776706"
            }
        }
    """
    return jsonify(sample=serialize(Sample.query.get_or_404(sample_id)))


@api.route('/samples', methods=['POST'])
@data(name={'type': 'string', 'required': True},
      pool_size={'type': 'integer'},
      coverage_profile={'type': 'boolean'},
      public={'type': 'boolean'})
@require_user
@ensure(has_role('admin'), has_role('importer'), satisfy=any)
def samples_add(data):
    """
    Create a sample.

    Requires the `admin` or `importer` role.

    :arg name: Human readable name.
    :type name: string
    :arg pool_size: Number of individuals (default: ``1``).
    :type pool_size: integer
    :arg coverage_profile: Whether or not this sample has a coverage profile
        (default: ``True``).
    :type coverage_profile: boolean
    :arg public: Whether or not this sample is public (default: ``False``).
    :type public: boolean
    :statuscode 201: Respond with a URI for the created sample as `sample`.

    Example request:

    .. sourcecode:: http

        POST /samples HTTP/1.1
        Content-Type: application/json

        {
          "name": "1KG phase 1 release",
          "pool_size": 1092,
          "coverage_profile": false,
          "public": true
        }

    Example response:

    .. sourcecode:: http

        HTTP/1.1 201 CREATED
        Location: https://example.com/samples/3
        Content-Type: application/json

        {
          "sample_uri": "/samples/3"
        }
    """
    sample = Sample(g.user,
                    data['name'],
                    pool_size=data.get('pool_size', 1),
                    coverage_profile=data.get('coverage_profile', True),
                    public=data.get('public', False))
    db.session.add(sample)
    db.session.commit()
    current_app.logger.info('Added sample: %r', sample)
    uri = url_for('.samples_get', sample_id=sample.id)
    response = jsonify(sample_uri=uri)
    response.location = uri
    return response, 201


@api.route('/samples/<int:sample_id>', methods=['PATCH'])
@data(active={'type': 'boolean'})
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def samples_update(data, sample_id):
    """
    Update a sample.

    Requires the `admin` role or being the owner of the requested sample.

    :arg active: If set to ``True`` or ``False``, activate or de-activate the
        sample, respectively.
    :type active: boolean
    :statuscode 200: Respond with a :ref:`sample <api_samples>` object as
        `sample`.

    Example request:

    .. sourcecode:: http

        PATCH /samples/3 HTTP/1.1
        Content-Type: application/json

        {
          "active": true
        }

    Example response:

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
          "sample":
            {
              "uri": "/samples/3",
              "user_uri": "/users/fred",
              "variations_uri": "/samples/3/variations",
              "coverages_uri": "/samples/3/coverages",
              "name": "1KG phase 1 release",
              "pool_size": 1092,
              "public": true,
              "added": "2012-11-23T10:55:12.776706"
            }
        }
    """
    # Todo: I'm not sure if this is really the pattern we want the API to use
    #     for updating objects. But works for now. Not sure if the 200 status
    #     is the correct one.
    sample = Sample.query.get_or_404(sample_id)
    for field, value in data.items():
        if field == 'active' and value:
            # Todo: Check if sample is ready to activate, e.g. if there are
            #     expected imported data sources and no imports running at the
            #     moment. Also, number of coverage tracks should be 0 or equal
            #     to pool size.
            #raise ActivationFailure('reason', 'This is the reason')
            sample.active = True
        else:
            abort(400)
    db.session.commit()
    return jsonify(sample=serialize(sample))


@api.route('/samples/<int:sample_id>/variations', methods=['GET'])
@collection
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def variations_list(begin, count, sample_id):
    """
    Collection of sets of observations in a sample.

    .. todo:: Documentation.
    """
    # Todo: Perhaps we could add a query string parameter to specify the
    #     fields that should be expanded: ?expand=data_source,sample
    sample = Sample.query.get_or_404(sample_id)
    variations = sample.variations
    return (variations.count(),
            jsonify(sample=serialize(sample),
                    variations=[serialize(v, expand=['data_source']) for v in
                                variations.limit(count).offset(begin)]))


@api.route('/samples/<int:sample_id>/variations/<int:variation_id>', methods=['GET'])
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def variations_get(sample_id, variation_id):
    """
    Set of observations details.

    .. warning:: Not implemented.
    """
    abort(501)


@api.route('/samples/<int:sample_id>/variations/<int:variation_id>/import_status', methods=['GET'])
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def variations_import_status(sample_id, variation_id):
    """
    Get set of observations import status.

    .. todo:: Documentation.
    """
    # Todo: Merge this with the `variations_get` endpoint.
    # Todo: We might want to handle the special (error) case where .imported
    #     is False but no .import_task_uuid is set, or the task with that uuid
    #     is not running. Instead of ready=True/False maybe this needs a
    #     status=pending/importing/ready and if it is pending a way to restart
    #     the import (it is now automatically imported when the Variation
    #     instance is created at .variations_add).
    variation = Variation.query.get_or_404(variation_id)
    percentage = None

    if variation.import_task_uuid:
        result = tasks.import_variation.AsyncResult(variation.import_task_uuid)
        try:
            # This re-raises a possible TaskError, handled by error_task_error
            # above.
            # Todo: Re-raising doesn't seem to work at the moment...
            result.get(timeout=3)
        except celery.exceptions.TimeoutError:
            pass
        if result.state == 'PROGRESS':
            percentage = result.info['percentage']

    uri = url_for('.variations_get', sample_id=sample_id, variation_id=variation_id)
    return jsonify(status={'variation_uri': uri, 'ready': variation.imported, 'percentage': percentage})


@api.route('/samples/<int:sample_id>/variations', methods=['POST'])
@data(data_source={'type': 'data_source', 'required': True})
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def variations_add(data, sample_id):
    """
    Create a set of observations.

    .. todo:: Documentation.
    """
    # Todo: Only if sample is not active.
    # Todo: Check for importer role.
    # Todo: If import fails, observations are removed by task cleanup, but we
    #     are still left with the variations instance. Not sure how to cleanup
    #     in that case.
    sample = Sample.query.get_or_404(sample_id)
    variation = Variation(sample, data['data_source'])
    db.session.add(variation)
    db.session.commit()
    current_app.logger.info('Added variation: %r', variation)
    result = tasks.import_variation.delay(variation.id)
    current_app.logger.info('Called task: import_variation(%d) %s', variation.id, result.task_id)
    uri = url_for('.variations_import_status', sample_id=sample.id, variation_id=variation.id)
    response = jsonify(variation_import_status_uri=uri)
    response.location = uri
    return response, 202


@api.route('/samples/<int:sample_id>/coverages', methods=['GET'])
@collection
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def coverages_list(begin, count, sample_id):
    """
    Collection of sets of regions in a sample.

    .. todo:: Documentation.
    """
    sample = Sample.query.get_or_404(sample_id)
    coverages = sample.coverages
    return (coverages.count(),
            jsonify(sample=serialize(sample),
                    coverages=[serialize(c, expand=['data_source']) for c in
                               coverages.limit(count).offset(begin)]))


@api.route('/samples/<int:sample_id>/coverages/<int:coverage_id>', methods=['GET'])
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def coverages_get(sample_id, coverage_id):
    """
    Set of regions details.

    .. warning:: Not implemented.
    """
    abort(501)


@api.route('/samples/<int:sample_id>/coverages/<int:coverage_id>/import_status', methods=['GET'])
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def coverages_import_status(sample_id, coverage_id):
    """
    Get set of regions import status.

    .. todo:: Documentation.
    """
    coverage = Coverage.query.get_or_404(coverage_id)
    percentage = None

    if coverage.import_task_uuid:
        result = tasks.import_coverage.AsyncResult(coverage.import_task_uuid)
        try:
            # This re-raises a possible TaskError, handled by error_task_error
            # above.
            result.get(timeout=3)
        except celery.exceptions.TimeoutError:
            pass
        if result.state == 'PROGRESS':
            percentage = result.info['percentage']

    uri = url_for('.coverages_get', sample_id=sample_id, coverage_id=coverage_id)
    return jsonify(status={'coverage_uri': uri, 'ready': coverage.imported, 'percentage': percentage})


@api.route('/samples/<int:sample_id>/coverages', methods=['POST'])
@data(data_source={'type': 'data_source', 'required': True})
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def coverages_add(data, sample_id):
    """
    Create a set of regions.

    .. todo:: Documentation.
    """
    # Todo: Only if sample is not active.
    # Todo: Check for importer role.
    sample = Sample.query.get_or_404(sample_id)
    coverage = Coverage(sample, data['data_source'])
    db.session.add(coverage)
    db.session.commit()
    current_app.logger.info('Added coverage: %r', coverage)
    result = tasks.import_coverage.delay(coverage.id)
    current_app.logger.info('Called task: import_coverage(%d) %s', coverage.id, result.task_id)
    uri = url_for('.coverages_import_status', sample_id=sample.id, coverage_id=coverage.id)
    response = jsonify(coverage_import_status_uri=uri)
    response.location = uri
    return response, 202


@api.route('/data_sources', methods=['GET'])
@collection
@data(user={'type': 'user'})
@require_user
@ensure(has_role('admin'), data_is_user('user'), satisfy=any)
def data_sources_list(begin, count, data):
    """
    Collection of data sources.

    Requires the `admin` role or being the user specified in the `user`
    argument.

    :arg user: If set to the URI for a user, restrict the collection to
        data sources owned by this user.
    :type user: string
    :statuscode 200: Respond with a list of :ref:`data source <api_data_sources>`
        objects as `data_sources`.

    Example request:

    .. sourcecode:: http

        GET /data_sources?user=%2Fusers%2Ffred HTTP/1.1

    Example response:

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
          "data_sources":
            [
              {
                "uri": "/data_sources/23",
                "user_uri": "/users/fred",
                "annotations_uri": "/data_sources/23/annotations",
                "data_uri": "/data_sources/23/data",
                "name": "1KG chromosome 20 SNPs",
                "filetype": "vcf",
                "gzipped": true,
                "added": "2012-11-23T10:55:12.776706"
              }
            ]
        }
    """
    data_sources = DataSource.query.filter_by(**data)
    return (data_sources.count(),
            jsonify(data_sources=[serialize(d) for d in
                                  data_sources.limit(count).offset(begin)]))


@api.route('/data_sources/<int:data_source_id>', methods=['GET'])
@require_user
@ensure(has_role('admin'), owns_data_source, satisfy=any)
def data_sources_get(data_source_id):
    """
    Details for data source.

    Requires the `admin` role or being the owner of the requested data source.

    :statuscode 200: Respond with a :ref:`data source <api_data_sources>`
        object as `data_source`.

    Example request:

    .. sourcecode:: http

        GET /data_sources/23 HTTP/1.1

    Example response:

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
          "data_source":
            {
              "uri": "/data_sources/23",
              "user_uri": "/users/fred",
              "annotations_uri": "/data_sources/23/annotations",
              "data_uri": "/data_sources/23/data",
              "name": "1KG chromosome 20 SNPs",
              "filetype": "vcf",
              "gzipped": true,
              "added": "2012-11-23T10:55:12.776706"
            }
        }
    """
    return jsonify(data_source=serialize(DataSource.query.get_or_404(
                data_source_id)))


@api.route('/data_sources/<int:data_source_id>/data', methods=['GET'])
@require_user
@ensure(has_role('admin'), owns_data_source, satisfy=any)
def data_sources_data(data_source_id):
    """
    Download data source data.

    Requires the `admin` role or being the owner of the requested data source.

    :statuscode 200: Respond with the data for the data source.

    Example request:

    .. sourcecode:: http

        GET /data_sources/23/data HTTP/1.1

    Example response:

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/x-gzip

        (gzipped data omitted...)
    """
    data_source = DataSource.query.get_or_404(data_source_id)
    return send_from_directory(current_app.config['FILES_DIR'],
                               data_source.filename,
                               mimetype='application/x-gzip')


@api.route('/data_sources', methods=['POST'])
@data(name={'type': 'string', 'required': True},
      filetype={'type': 'string', 'allowed': DATA_SOURCE_FILETYPES,
                'required': True},
      gzipped={'type': 'boolean'},
      local_path={'type': 'string'})
@require_user
def data_sources_add(data):
    """
    Create a data source.

    The data should be either attached as a HTTP file upload called `data` or
    specified by the `local_path` argument.

    :arg name: Human readable name.
    :type name: string
    :arg filetype: Data filetype.
    :type filetype: string
    :arg gzipped: Whether or not data is compressed (default: ``False``).
    :type gzipped: boolean
    :arg local_path: A path to the data on the local server file system
        (optional).
    :type local_path: string
    :statuscode 201: Respond with a URI for the created data source as
        `data_source`.

    Example request:

    .. sourcecode:: http

        POST /data_sources HTTP/1.1
        Content-Type: application/json

        {
          "name": "1KG chromosome 20 SNPs",
          "filetype": "vcf",
          "gzipped": true,
          "local_path": "/var/upload/users/fred/1kg_snp_chr20.vcf.gz"
        }

    Example response:

    .. sourcecode:: http

        HTTP/1.1 201 CREATED
        Location: https://example.com/data_sources/23
        Content-Type: application/json

        {
          "data_source_uri": "/data_sources/23"
        }
    """
    # Todo: If files['data'] is missing (or non-existent file?), we crash with
    #     a data_source_not_cached error.
    # Todo: Sandbox local_path.
    # Todo: Option to upload the actual data later at the /data_source/XX/data
    #     endpoint, symmetrical to the GET request.
    data_source = DataSource(g.user,
                             data['name'],
                             data['filetype'],
                             upload=request.files.get('data'),
                             local_path=data.get('local_path'),
                             gzipped=data.get('gzipped', False))
    db.session.add(data_source)
    db.session.commit()
    current_app.logger.info('Added data source: %r', data_source)
    uri = url_for('.data_sources_get', data_source_id=data_source.id)
    response = jsonify(data_source_uri=uri)
    response.location = uri
    return response, 201


@api.route('/data_sources/<int:data_source_id>/annotations', methods=['GET'])
@collection
@require_user
@ensure(has_role('admin'), owns_data_source, satisfy=any)
def annotations_list(begin, count, data_source_id):
    """
    Collection of annotations for a data source.

    Requires the `admin` role or being the owner of the data source.

    :statuscode 200: Respond with a list of :ref:`annotation <api_annotations>`
        objects as `annotations`.

    Example request:

    .. sourcecode:: http

        GET /data_sources/23/annotations HTTP/1.1

    Example response:

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
          "annotations":
            [
              {
                "uri": "/data_sources/23/annotations/2",
                "original_data_source_uri": "/data_sources/23",
                "annotated_data_source_uri": "/data_sources/57"
              },
              {
                "uri": "/data_sources/23/annotations/3",
                "original_data_source_uri": "/data_sources/23",
                "annotated_data_source_uri": "/data_sources/58"
              },
              {
                "uri": "/data_sources/23/annotations/4",
                "original_data_source_uri": "/data_sources/23",
                "annotated_data_source_uri": "/data_sources/59"
              }
            ]
        }
    """
    annotations = DataSource.query.get_or_404(data_source_id).annotations
    return (annotations.count(),
            jsonify(annotations=[serialize(a) for a in
                                 annotations.limit(count).offset(begin)]))


@api.route('/data_sources/<int:data_source_id>/annotations/<int:annotation_id>',
           methods=['GET'])
@require_user
@ensure(has_role('admin'), owns_data_source, satisfy=any)
def annotations_get(data_source_id, annotation_id):
    """
    Details for annotation.

    Requires the `admin` role or being the owner of the data source.

    :statuscode 200: Respond with an :ref:`annotation <api_annotations>`
        object as `annotation`.

    Example request:

    .. sourcecode:: http

        GET /data_sources/23/annotations/2 HTTP/1.1

    Example response:

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
          "annotation":
            {
              "uri": "/data_sources/23/annotations/2",
              "original_data_source_uri": "/data_sources/23",
              "annotated_data_source_uri": "/data_sources/57"
            }
        }
    """
    annotation = Annotation.query.get_or_404(annotation_id)
    if not annotation.written:
        abort(404)
    return jsonify(annotation=serialize(annotation))


@api.route('/data_sources/<int:data_source_id>/annotations/<int:annotation_id>/write_status', methods=['GET'])
@require_user
@ensure(has_role('admin'), owns_data_source, satisfy=any)
def annotations_write_status(data_source_id, annotation_id):
    """
    Get annotation write status.

    .. todo: Documentation.
    """
    annotation = Annotation.query.get_or_404(annotation_id)
    percentage = None

    # Todo: If annotation.written, return immediately. What to do if there's
    #     no annotation.write_task_uuid?

    if annotation.write_task_uuid:
        result = tasks.write_annotation.AsyncResult(annotation.write_task_uuid)
        try:
            # This re-raises a possible TaskError, handled by error_task_error
            # above.
            result.get(timeout=3)
        except celery.exceptions.TimeoutError:
            pass
        if result.state == 'PROGRESS':
            percentage = result.info['percentage']

    uri = url_for('.annotations_get', data_source_id=data_source_id, annotation_id=annotation_id)
    return jsonify(status={'annotation_uri': uri, 'ready': annotation.written, 'percentage': percentage})


@api.route('/data_sources/<int:data_source_id>/annotations', methods=['POST'])
@data(global_frequencies={'type': 'boolean'},
      exclude_samples={'type': 'list', 'schema': {'type': 'sample'}},
      include_samples={'type': 'list',
                       'schema': {'type': 'list',
                                  'items': [{'type': 'string'},
                                            {'type': 'sample'}]}})
@require_user
@ensure(has_role('admin'), owns_data_source, has_role('annotator'),
        has_role('trader'),
        satisfy=lambda conditions: next(conditions) or (next(conditions) and any(conditions)))
def annotations_add(data, data_source_id):
    """
    Annotate a data source.

    .. todo: Documentation.
    """
    # Todo: Check if data source is a VCF file.
    # Todo: The `include_samples` might be better structured as a list of
    #     objects, e.g. ``[{label: GoNL, sample: ...}, {label: 1KG, sample: ...}]``.
    # The `satisfy` keyword argument used here in the `ensure` decorator means
    # that we ensure at least one of:
    # - admin
    # - owns_data_source AND annotator
    # - owns_data_source AND trader
    exclude_samples = data.get('exclude_samples', [])

    # Todo: Perhaps a better name would be `local_frequencies` instead of
    #     `include_sample_ids`, to contrast with the `global_frequencies`
    #     flag.
    include_samples = dict(data.get('include_samples', []))

    if not all(re.match('[0-9A-Z]+', label) for label in include_samples):
        raise ValidationError('Labels for inluded samples must contain only'
                              ' uppercase alphanumeric characters')

    for sample in include_samples.values():
        if not (sample.public or
                sample.user is g.user or
                'admin' in g.user.roles):
            # Todo: Meaningful error message.
            abort(400)

    original_data_source = DataSource.query.get(data_source_id)
    if original_data_source is None:
        abort(400)

    if 'admin' not in g.user.roles and 'annotator' not in g.user.roles:
        # This is a trader, so check if the data source has been imported in
        # an active sample.
        # Todo: Anyone should be able to annotate against the public samples.
        if not original_data_source.variations.join(Sample).filter_by(active=True).count():
            raise InvalidDataSource('inactive_data_source', 'Data source '
                'cannot be annotated unless it is imported in an active sample')

    annotated_data_source = DataSource(g.user,
                                       '%s (annotated)' % original_data_source.name,
                                       original_data_source.filetype,
                                       empty=True, gzipped=True)
    db.session.add(annotated_data_source)
    annotation = Annotation(original_data_source, annotated_data_source)
    db.session.add(annotation)
    db.session.commit()
    current_app.logger.info('Added data source: %r', annotated_data_source)
    current_app.logger.info('Added annotation: %r', annotation)

    result = tasks.write_annotation.delay(annotation.id,
                                          global_frequencies=data.get('global_frequencies', False),
                                          exclude_sample_ids=[sample.id for sample in exclude_samples],
                                          include_sample_ids={label: sample.id for label, sample in include_samples.items()})
    current_app.logger.info('Called task: write_annotation(%d) %s', annotation.id, result.task_id)
    uri = url_for('.annotations_write_status', data_source_id=original_data_source.id, annotation_id=annotation.id)
    response = jsonify(annotation_write_status_uri=uri)
    response.location = uri
    return response, 202


@api.route('/check_variant', methods=['POST'])
@require_user
@ensure(has_role('admin'), has_role('annotator'), satisfy=any)
def check_variant():
# Todo: Make this a GET request?
# We also want to check frequencies. For example::
#
#   SELECT COUNT(*) FROM Observation, Sample
#     WHERE Observation.sampleId = Sample.id
#     AND Observation.variantId = %i
#     AND Sample.id > 100
#     AND Sample.id NOT IN (%s)
#
# will be something like::
#
#   Observation.query.join(Sample).filter(Observation.variant_id == 1).
#                                       filter(Sample.id == 1).count()
    data = request.json or request.form
    try:
        # Todo: use normalize_chromosome from tasks.py.
        chromosome = data['chromosome']
        begin = int(data['begin'])
        end = int(data['end'])
        reference = data['reference']
        alternate = data['alternate']
    except (KeyError, ValueError):
        abort(400)
    observations = Observation.query.filter_by(chromosome=chromosome, begin=begin, end=end, reference=reference, variant=alternate).count()
    current_app.logger.info('Checked variant: chromosome %s, begin %d, end %d, reference %s, alternate %s', chromosome, begin, end, reference, alternate)
    return jsonify(observations=observations)
