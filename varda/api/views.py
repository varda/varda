"""
REST API views.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from functools import wraps
import os
import re
import urlparse
import uuid

from celery.exceptions import TimeoutError
from flask import abort, Blueprint, current_app, g, jsonify, redirect, request, send_from_directory, url_for
from werkzeug.exceptions import HTTPException

from .. import db, genome
from ..models import Annotation, Coverage, DataSource, InvalidDataSource, Observation, Sample, User, Variation
from ..tasks import write_annotation, import_variation, import_coverage, TaskError
from .errors import ActivationFailure
from .permissions import ensure, has_login, has_role, owns_data_source, owns_sample, require_user
from .serialize import serialize
from .utils import parse_args, parse_bool, parse_dict, parse_list


API_VERSION = 1


api = Blueprint('api', __name__)


def get_data_source_id(uri):
    """
    Get a data source identifier from its uri.
    """
    args = parse_args(current_app, data_sources_get, uri)
    return args['data_source_id']


def get_sample_id(uri):
    """
    Get a sample identifier from its uri.
    """
    args = parse_args(current_app, samples_get, uri)
    return args['sample_id']


def get_user(login, password):
    """
    Check if login and password are correct and return the user if so, else
    return ``None``.
    """
    user = User.query.filter_by(login=login).first()
    if user is not None and user.check_password(password):
        return user


@api.before_request
def register_user():
    """
    Make sure we add a :class:`.User` instance to the global objects if we
    have authentication.
    """
    auth = request.authorization
    g.user = get_user(auth.username, auth.password) if auth else None
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


@api.errorhandler(TaskError)
def error_task_error(error):
    return jsonify(error=serialize(error)), 500


@api.errorhandler(InvalidDataSource)
def error_invalid_data_source(error):
    return jsonify(error=serialize(error)), 400


@api.errorhandler(ActivationFailure)
def error_activation_failure(error):
    return jsonify(error=serialize(error)), 400


@api.route('/')
def apiroot():
    api = {'status':  'ok',
           'version': API_VERSION,
           'genome':  genome.keys(),
           'collections': {
               'users':        url_for('.users_list'),
               'samples':      url_for('.samples_list'),
               'data_sources': url_for('.data_sources_list')}}
    return jsonify(api=api)


@api.route('/authentication')
def authentication():
    """
    Return current authentication state.
    """
    authentication = {'authenticated': False}
    if g.user is not None:
        authentication.update(authenticated=True, user=serialize(g.user))
    return jsonify(authentication=authentication)


@api.route('/users', methods=['GET'])
@require_user
@ensure(has_role('admin'))
def users_list():
    """
    Details for all registered users.

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
                "uri": "/users/34",
                "name": "Frederick Sanger",
                "login": "fred",
                "roles": ["admin"],
                "added": "2012-11-23T10:55:12.776706"
              },
              {
                "uri": "/users/35",
                "name": "Walter Gilbert",
                "login": "walter",
                "roles": ["importer", "annotator"],
                "added": "2012-11-23T10:55:12.776706"
              }
            ]
        }
    """
    return jsonify(users=[serialize(u) for u in User.query])


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

        GET /users/34 HTTP/1.1

    Example response:

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
          "user":
            {
              "uri": "/users/34",
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
@require_user
@ensure(has_role('admin'))
def users_add():
    """
    Create a new user.

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

        POST /users/34 HTTP/1.1
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
        Location: http://example.com/users/fred
        Content-Type: application/json

        {
          "user": "/users/fred"
        }
    """
    # Todo: Validate login (alphanumeric).
    # Todo: Check for duplicate login.
    # Todo: Optionally generate password.
    data = request.json or request.form
    try:
        name = data.get('name', data['login'])
        login = data['login']
        password = data['password']
        roles = parse_list(data['roles'])
    except KeyError:
        abort(400)
    user = User(name, login, password, roles)
    db.session.add(user)
    db.session.commit()
    current_app.logger.info('Added user: %r', user)
    uri = url_for('.users_get', login=user.login)
    response = jsonify(user=uri)
    response.location = uri
    return response, 201


@api.route('/samples', methods=['GET'])
@require_user
@ensure(has_role('admin'))
def samples_list():
    """

    Example usage::

        curl -i -u pietje:pi3tje http://127.0.0.1:5000/samples
    """
    return jsonify(samples=[serialize(s) for s in Sample.query])


@api.route('/samples/<int:sample_id>', methods=['GET'])
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def samples_get(sample_id):
    """

    Example usage::

        curl -i http://127.0.0.1:5000/samples/2
    """
    return jsonify(sample=serialize(Sample.query.get_or_404(sample_id)))


@api.route('/samples', methods=['POST'])
@require_user
@ensure(has_role('admin'), has_role('importer'), satisfy=any)
def samples_add():
    """

    Example usage::

        curl -i -d 'name=My big sequencing experiment' -d 'pool_size=500' http://127.0.0.1:5000/samples
    """
    data = request.json or request.form
    try:
        name = data['name']
        pool_size = int(data.get('pool_size', 1))
        public = parse_bool(data.get('public', False))
        coverage_profile = parse_bool(data.get('coverage_profile', False))
    except (KeyError, ValueError):
        abort(400)
    sample = Sample(g.user, name, pool_size=pool_size, public=public, coverage_profile=coverage_profile)
    db.session.add(sample)
    db.session.commit()
    current_app.logger.info('Added sample: %r', sample)
    uri = url_for('.samples_get', sample_id=sample.id)
    response = jsonify(sample=uri)
    response.location = uri
    return response, 201


@api.route('/samples/<int:sample_id>', methods=['PATCH'])
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def samples_update(sample_id):
    """

    Example usage::

        curl -X PATCH -d 'active=true' http://127.0.0.1:5000/samples/3
    """
    # Todo: I'm not sure if this is really the pattern we want the API to use
    #     for updating objects. But works for now.
    sample = Sample.query.get_or_404(sample_id)
    data = request.json or request.form
    for field, value in data.items():
        if field == 'active' and parse_bool(value):
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
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def variations_list(sample_id):
    """
    Get variations in a sample.
    """
    # Todo.
    #return jsonify(variations=[serialize(v) for v in Sample.query.get_or_404(sample_id).variations])
    abort(501)


@api.route('/samples/<int:sample_id>/variations/<int:variation_id>', methods=['GET'])
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def variations_get(sample_id, variation_id):
    """
    Get variation.
    """
    # Todo.
    #return jsonify(variation=serialize(Variation.query.get_or_404(variation_id)))
    abort(501)


@api.route('/samples/<int:sample_id>/variations/<int:variation_id>/import_status', methods=['GET'])
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def variations_import_status(sample_id, variation_id):
    """
    Get variation import status.
    """
    # Todo: We might want to handle the special (error) case where .imported
    #     is False but no .import_task_uuid is set, or the task with that uuid
    #     is not running. Instead of ready=True/False maybe this needs a
    #     status=pending/importing/ready and if it is pending a way to restart
    #     the import (it is now automatically imported when the Variation
    #     instance is created at .variations_add).
    variation = Variation.query.get_or_404(variation_id)
    percentage = None

    if variation.import_task_uuid:
        result = import_variation.AsyncResult(variation.import_task_uuid)
        try:
            # This re-raises a possible TaskError, handled by error_task_error
            # above.
            # Todo: Re-raising doesn't seem to work at the moment...
            result.get(timeout=3)
        except TimeoutError:
            pass
        if result.state == 'PROGRESS':
            percentage = result.info['percentage']

    uri = url_for('.variations_get', sample_id=sample_id, variation_id=variation_id)
    return jsonify(status={'variation': uri, 'ready': variation.imported, 'percentage': percentage})


@api.route('/samples/<int:sample_id>/variations', methods=['POST'])
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def variations_add(sample_id):
    """

    Example usage::

        curl -i -d 'data_source=/data_sources/3' http://127.0.0.1:5000/samples/1/variations
    """
    # Todo: Only if sample is not active.
    # Todo: Check for importer role.
    # Todo: If import fails, observations are removed by task cleanup, but we
    #     are still left with the variations instance. Not sure how to cleanup
    #     in that case.
    data = request.json or request.form
    try:
        data_source_id = get_data_source_id(data['data_source'])
    except (KeyError, ValueError):
        abort(400)
    sample = Sample.query.get_or_404(sample_id)
    data_source = DataSource.query.get(data_source_id)
    if data_source is None:
        abort(400)
    variation = Variation(sample, data_source)
    db.session.add(variation)
    db.session.commit()
    current_app.logger.info('Added variation: %r', variation)
    result = import_variation.delay(variation.id)
    current_app.logger.info('Called task: import_variation(%d) %s', variation.id, result.task_id)
    uri = url_for('.variations_import_status', sample_id=sample.id, variation_id=variation.id)
    response = jsonify(variation_import_status=uri)
    response.location = uri
    return response, 202


@api.route('/samples/<int:sample_id>/coverages', methods=['GET'])
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def coverages_list(sample_id):
    """
    Get coverages in a sample.
    """
    # Todo.
    abort(501)


@api.route('/samples/<int:sample_id>/coverages/<int:coverage_id>', methods=['GET'])
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def coverages_get(sample_id, coverage_id):
    """
    Get coverage.
    """
    # Todo.
    abort(501)


@api.route('/samples/<int:sample_id>/coverages/<int:coverage_id>/import_status', methods=['GET'])
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def coverages_import_status(sample_id, coverage_id):
    """
    Get coverage import status.
    """
    coverage = Coverage.query.get_or_404(coverage_id)
    percentage = None

    if coverage.import_task_uuid:
        result = import_coverage.AsyncResult(coverage.import_task_uuid)
        try:
            # This re-raises a possible TaskError, handled by error_task_error
            # above.
            result.get(timeout=3)
        except TimeoutError:
            pass
        if result.state == 'PROGRESS':
            percentage = result.info['percentage']

    uri = url_for('.coverages_get', sample_id=sample_id, coverage_id=coverage_id)
    return jsonify(status={'coverage': uri, 'ready': coverage.imported, 'percentage': percentage})


@api.route('/samples/<int:sample_id>/coverages', methods=['POST'])
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def coverages_add(sample_id):
    """

    Example usage::

        curl -i -d 'data_source=/data_sources/3' http://127.0.0.1:5000/samples/1/coverages
    """
    # Todo: Only if sample is not active.
    # Todo: Check for importer role.
    data = request.json or request.form
    try:
        data_source_id = get_data_source_id(data['data_source'])
    except (KeyError, ValueError):
        abort(400)
    sample = Sample.query.get_or_404(sample_id)
    data_source = DataSource.query.get(data_source_id)
    if data_source is None:
        abort(400)
    coverage = Coverage(sample, data_source)
    db.session.add(coverage)
    db.session.commit()
    current_app.logger.info('Added coverage: %r', coverage)
    result = import_coverage.delay(coverage.id)
    current_app.logger.info('Called task: import_coverage(%d) %s', coverage.id, result.task_id)
    uri = url_for('.coverages_import_status', sample_id=sample.id, coverage_id=coverage.id)
    response = jsonify(coverage_import_status=uri)
    response.location = uri
    return response, 202


@api.route('/data_sources', methods=['GET'])
@require_user
@ensure(has_role('admin'))
def data_sources_list():
    """
    List all data_sources.
    """
    return jsonify(data_sources=[serialize(d) for d in DataSource.query])


@api.route('/data_sources/<int:data_source_id>', methods=['GET'])
@require_user
@ensure(has_role('admin'), owns_data_source, satisfy=any)
def data_sources_get(data_source_id):
    """
    Get data source.
    """
    return jsonify(data_source=serialize(DataSource.query.get_or_404(data_source_id)))


@api.route('/data_sources/<int:data_source_id>/data', methods=['GET'])
@require_user
@ensure(has_role('admin'), owns_data_source, satisfy=any)
def data_sources_data(data_source_id):
    """
    Download data source data.
    """
    data_source = DataSource.query.get_or_404(data_source_id)
    # Todo: Choose mimetype.
    return send_from_directory(current_app.config['FILES_DIR'], data_source.filename, mimetype='application/x-gzip')


@api.route('/data_sources', methods=['POST'])
@require_user
def data_sources_add():
    """
    Upload VCF or BED file.

    .. todo:: It might be better to use the mimetype for filetype here instead
        of a separate field.
    .. todo:: Have an option to add data source by external url instead of
        upload.
    """
    data = request.json or request.form
    try:
        name = data['name']
        filetype = data['filetype']
    except KeyError:
        abort(400)
    gzipped = parse_bool(data.get('gzipped', False))
    data_arg = request.files.get('data')
    local_path = data.get('local_path')
    data_source = DataSource(g.user, name, filetype, upload=data_arg, local_path=local_path, gzipped=gzipped)
    db.session.add(data_source)
    db.session.commit()
    current_app.logger.info('Added data source: %r', data_source)
    uri = url_for('.data_sources_get', data_source_id=data_source.id)
    response = jsonify(data_source=uri)
    response.location = uri
    return response, 201


@api.route('/data_sources/<int:data_source_id>/annotations', methods=['GET'])
@require_user
@ensure(has_role('admin'), owns_data_source, satisfy=any)
def annotations_list(data_source_id):
    """
    Get annotated versions of a data source.
    """
    return jsonify(annotations=[serialize(a) for a in DataSource.query.get_or_404(data_source_id).annotations])


@api.route('/data_sources/<int:data_source_id>/annotations/<int:annotation_id>', methods=['GET'])
@require_user
@ensure(has_role('admin'), owns_data_source, satisfy=any)
def annotations_get(data_source_id, annotation_id):
    """
    Get annotated version of a data source.
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
    """
    annotation = Annotation.query.get_or_404(annotation_id)
    percentage = None

    # Todo: If annotation.written, return immediately. What to do if there's
    #     no annotation.write_task_uuid?

    if annotation.write_task_uuid:
        result = write_annotation.AsyncResult(annotation.write_task_uuid)
        try:
            # This re-raises a possible TaskError, handled by error_task_error
            # above.
            result.get(timeout=3)
        except TimeoutError:
            pass
        if result.state == 'PROGRESS':
            percentage = result.info['percentage']

    uri = url_for('.annotations_get', data_source_id=data_source_id, annotation_id=annotation_id)
    return jsonify(status={'annotation': uri, 'ready': annotation.written, 'percentage': percentage})


@api.route('/data_sources/<int:data_source_id>/annotations', methods=['POST'])
@require_user
@ensure(has_role('admin'), owns_data_source, has_role('annotator'),
        has_role('trader'),
        satisfy=lambda conditions: next(conditions) or (next(conditions) and any(conditions)))
def annotations_add(data_source_id):
    """
    Annotate a data source.

    .. todo:: Support other formats than VCF (and check that this is not e.g. a
        BED data source, which of course cannot be annotated).
    """
    # The `satisfy` keyword argument used here in the `ensure` decorator means
    # that we ensure at least one of:
    # - admin
    # - owns_data_source AND annotator
    # - owns_data_source AND trader
    data = request.json or request.form

    global_frequencies = parse_bool(data.get('global_frequencies', False))

    try:
        exclude_sample_ids = [get_sample_id(sample) for sample
                              in parse_list(data['exclude_samples'])]
    except KeyError:
        exclude_sample_ids = []
    except ValueError:
        abort(400)

    for sample_id in exclude_sample_ids:
        sample = Sample.query.get(sample_id)
        if sample is None:
            abort(400)

    # Example: "1KG=/samples/34,GONL=/samples/7"
    # Todo: Perhaps a better name would be `local_frequencies` instead of
    #     `include_sample_ids`, to contrast with the `global_frequencies`
    #     flag.
    try:
        include_sample_ids = {label: get_sample_id(sample) for label, sample
                              in parse_dict(data['include_samples']).items()}
    except KeyError:
        include_sample_ids = {}
    except ValueError:
        abort(400)

    for label in include_sample_ids:
        if not re.match('[0-9A-Z]+', label):
            abort(400)

    for sample_id in include_sample_ids.values():
        sample = Sample.query.get(sample_id)
        if sample is None or not sample.active:
            abort(400)
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

    annotated_data_source = DataSource(g.user, '%s (annotated)' % original_data_source.name, original_data_source.filetype, empty=True, gzipped=True)
    db.session.add(annotated_data_source)
    annotation = Annotation(original_data_source, annotated_data_source)
    db.session.add(annotation)
    db.session.commit()
    current_app.logger.info('Added data source: %r', annotated_data_source)
    current_app.logger.info('Added annotation: %r', annotation)

    result = write_annotation.delay(annotation.id, global_frequencies=global_frequencies, exclude_sample_ids=exclude_sample_ids, include_sample_ids=include_sample_ids)
    current_app.logger.info('Called task: write_annotation(%d) %s', annotation.id, result.task_id)
    uri = url_for('.annotations_write_status', data_source_id=original_data_source.id, annotation_id=annotation.id)
    response = jsonify(annotation_write_status=uri)
    response.location = uri
    return response, 202


@api.route('/check_variant', methods=['POST'])
@require_user
@ensure(has_role('admin'), has_role('annotator'), satisfy=any)
def check_variant():
    """
    Check a variant.

    .. todo:: Make this a GET request?

    We also want to check frequencies. For example::

        SELECT COUNT(*) FROM Observation, Sample
        WHERE Observation.sampleId = Sample.id
        AND Observation.variantId = %i
        AND Sample.id > 100
        AND Sample.id NOT IN (%s)

    will be something like::

        Observation.query.join(Sample).filter(Observation.variant_id == 1).\\
                                       filter(Sample.id == 1).count()
    """
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
