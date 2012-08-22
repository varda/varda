"""
REST server views.

.. todo:: Representations of resources can sometimes be nested arbitrarily
    deeply.
    One extreme would be to only represent nested resources by their URL, the
    other extreme would be to always give the full JSON representation of the
    nested resource (unless the nesting is infinitely deep of course). A
    possible solution is to add a ?depth=N query parameter to view URLs, where
    N would be how deep to expand URLs with JSON representations. A nice
    implementation for this on the server side will require some thinking...
    Also see `this discussion <http://news.ycombinator.com/item?id=3491227>`_.

.. todo:: Use caching headers whenever we can. ETag headers are good when you
    can easily reduce a resource to a hash value. Last-Modified should
    indicate to you that keeping around a timestamp of when resources are
    updated is a good idea. Cache-Control and Expires should be given sensible
    values.

.. todo:: Implement pagination for collection representations, perhaps with
    HTTP range headers. This is related to sorting and filtering. See e.g.
    `this document <http://dojotoolkit.org/reference-guide/quickstart/rest.html>`_.

.. todo:: Use accept HTTP headers.
.. todo:: `Correctly use HTTP verbs <http://news.ycombinator.com/item?id=3514668>`_.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from functools import wraps
import os
import uuid

from celery.exceptions import TimeoutError
from flask import abort, Blueprint, current_app, g, jsonify, redirect, request, send_from_directory, url_for

from .. import db, log
from ..models import Annotation, DataSource, InvalidDataSource, Observation, Sample, User, Variant
from ..tasks import annotate_vcf, import_bed, import_vcf, TaskError
from .permissions import ensure, has_login, has_role, owns_data_source, owns_sample, require_user
from .serialize import serialize


API_VERSION = 1


api = Blueprint('api', __name__)


def get_user(login, password):
    """
    Check if login and password are correct and return the user if so, else
    return ``None``.
    """
    user = User.query.filter_by(login=login).first()
    if user is not None and user.check_password(password):
        return user


@api.before_request
def before_request():
    """
    Make sure we add a :class:`User` instance to the global objects if we have
    authentication.
    """
    auth = request.authorization
    g.user = get_user(auth.username, auth.password) if auth else None
    if auth and g.user is None:
        log.info('Unsuccessful authentication with username "%s"', auth.username)


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


@api.errorhandler(TaskError)
def error_task_error(error):
    return jsonify(error=serialize(error)), 500


@api.errorhandler(InvalidDataSource)
def error_invalid_data_source(error):
    return jsonify(error=serialize(error)), 400


@api.route('/')
def apiroot():
    api = {'status':  'ok',
           'version': API_VERSION,
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

    Example usage::

        curl -i -u pietje:pi3tje http://127.0.0.1:5000/users
    """
    return jsonify(users=[serialize(u) for u in User.query])


@api.route('/users/<login>', methods=['GET'])
@require_user
@ensure(has_role('admin'), has_login, satisfy=any)
def users_get(login):
    """

    Example usage::

        curl -i http://127.0.0.1:5000/users/pietje
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
    .. note:: Roles must be listed in a string separated by a comma.

    .. todo:: Check for duplicate login.
    .. todo:: Optionally generate password.
    """
    data = request.json or request.form
    try:
        name = data.get('name', data['login'])
        login = data['login']
        password = data['password']
        roles = data['roles'].split(',')
    except KeyError:
        abort(400)
    user = User(name, login, password, roles)
    db.session.add(user)
    db.session.commit()
    log.info('Added user: %r', user)
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
        coverage_threshold = int(data.get('coverage_threshold', 8))
        pool_size = int(data.get('pool_size', 1))
    except (KeyError, ValueError):
        abort(400)
    sample = Sample(g.user, name, coverage_threshold, pool_size)
    db.session.add(sample)
    db.session.commit()
    log.info('Added sample: %r', sample)
    uri = url_for('.samples_get', sample_id=sample.id)
    response = jsonify(sample=uri)
    response.location = uri
    return response, 201


@api.route('/samples/<int:sample_id>', methods=['PUT'])
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def samples_update(sample_id):
    """

    Example usage::

        curl -X PUT -d 'active=true' http://127.0.0.1:5000/samples/3
    """
    # Todo: I'm not sure if this is really the pattern we want the API to use
    #     for updating objects. But works for now.
    sample = Sample.query.get_or_404(sample_id)
    data = request.json or request.form
    for field, value in data.items():
        if field == 'active' and str(value).lower() == 'true':
            # Todo: Check if sample is ready to activate, e.g. if there are
            #     expected imported data sources and no imports running at the
            #     moment.
            sample.active = True
        else:
            abort(400)
    db.session.commit()
    return jsonify(sample=serialize(sample))


@api.route('/observations/wait/<task_id>', methods=['GET'])
@require_user
def observations_wait(task_id):
    """
    Check status of import observations task.

    .. todo:: Merge with other ``*_wait`` functions.

    .. note:: For a non-existing ``task_id``, ``.AsyncResult`` just returns a
        result with status ``PENDING``.
    """
    # In our unit tests we use CELERY_ALWAYS_EAGER, but in that case we can
    # not get the task result afterwards anymore via .AsyncResult. We know it
    # has been finished though, so we just return.
    if current_app.config.get('CELERY_ALWAYS_EAGER'):
        return jsonify(observations={'task_id': task_id, 'ready': True})
    result = import_vcf.AsyncResult(task_id)
    try:
        # This re-raises a possible TaskError, handled by the error_task_error
        # errorhandler above.
        result.get(timeout=3)
        ready = True
    except TimeoutError:
        ready = False
    return jsonify(observations={'task_id': task_id, 'ready': ready})


@api.route('/samples/<int:sample_id>/observations', methods=['POST'])
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def observations_add(sample_id):
    """

    Example usage::

        curl -i -d 'data_source=/data_sources/3' http://127.0.0.1:5000/samples/1/observations
    """
    data = request.json or request.form
    try:
        # Todo: Get internal ID in a more elegant way from URI
        data_source_id = int(data['data_source'].split('/')[-1])
    except (KeyError, ValueError):
        abort(400)
    Sample.query.get_or_404(sample_id)
    DataSource.query.get_or_404(data_source_id)
    result = import_vcf.delay(sample_id, data_source_id)
    log.info('Called task: import_vcf(%d, %d) %s', sample_id, data_source_id, result.task_id)
    uri = url_for('.observations_wait', task_id=result.task_id)
    response = jsonify(wait=uri)
    response.location = uri
    return response, 202


@api.route('/regions/wait/<task_id>', methods=['GET'])
@require_user
def regions_wait(task_id):
    """
    Check status of import regions task.

    .. todo:: Merge with other ``*_wait`` functions.
    """
    # In our unit tests we use CELERY_ALWAYS_EAGER, but in that case we can
    # not get the task result afterwards anymore via .AsyncResult. We know it
    # has been finished though, so we just return.
    if current_app.config.get('CELERY_ALWAYS_EAGER'):
        return jsonify(regions={'task_id': task_id, 'ready': True})
    result = import_bed.AsyncResult(task_id)
    try:
        # This re-raises a possible TaskError, handled by the error_task_error
        # errorhandler above.
        result.get(timeout=3)
        ready = True
    except TimeoutError:
        ready = False
    return jsonify(regions={'task_id': task_id, 'ready': ready})


@api.route('/samples/<int:sample_id>/regions', methods=['POST'])
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def regions_add(sample_id):
    """

    Example usage::

        curl -i -d 'data_source=3' http://127.0.0.1:5000/samples/1/regions

    .. todo:: Check for importer role.
    """
    data = request.json or request.form
    try:
        # Todo: Get internal ID in a more elegant way from URI
        data_source_id = int(data['data_source'].split('/')[-1])
    except (KeyError, ValueError):
        abort(400)
    result = import_bed.delay(sample_id, data_source_id)
    log.info('Called task: import_bed(%d, %d) %s', sample_id, data_source_id, result.task_id)
    uri = url_for('.regions_wait', task_id=result.task_id)
    response = jsonify(wait=uri)
    response.location = uri
    return response, 202


@api.route('/data_sources', methods=['GET'])
@require_user
@ensure(has_role('admin'))
def data_sources_list():
    """
    List all uploaded files.
    """
    return jsonify(data_sources=[serialize(d) for d in DataSource.query])


@api.route('/data_sources/<int:data_source_id>', methods=['GET'])
@require_user
@ensure(has_role('admin'), owns_data_source, satisfy=any)
def data_sources_get(data_source_id):
    """
    Get an uploaded file id.
    """
    return jsonify(data_source=serialize(DataSource.query.get_or_404(data_source_id)))


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
    rdata = request.json or request.form
    try:
        name = rdata['name']
        filetype = rdata['filetype']
    except KeyError:
        abort(400)
    gzipped = rdata.get('gzipped', '').lower() == 'true'
    data = request.files.get('data')
    local_path = request.form.get('local_path')
    data_source = DataSource(g.user, name, filetype, upload=data, local_path=local_path, gzipped=gzipped)
    db.session.add(data_source)
    db.session.commit()
    log.info('Added data source: %r', data_source)
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
    if annotation.data_source_id != data_source_id:
        abort(404)
    return send_from_directory(*os.path.split(annotation.local_path()), mimetype='application/x-gzip')


@api.route('/annotations/wait/<task_id>', methods=['GET'])
@require_user
def annotations_wait(task_id):
    """
    Wait for annotated version of a data source.

    .. todo:: Merge with other ``*_wait`` functions.
    """
    # In our unit tests we use CELERY_ALWAYS_EAGER, but in that case we can
    # not get the task result afterwards anymore via .AsyncResult. We know it
    # has been finished though, so we just return.
    # This does mean that we cannot add the full annotation data to this
    # response. See annotations_add for how to get this in the unit tests.
    # Note that the API thus diverges a bit for the unit tests.
    if current_app.config.get('CELERY_ALWAYS_EAGER'):
        return jsonify(annotation={'task_id': task_id, 'ready': True})
    annotation = {'task_id': task_id}
    result = annotate_vcf.AsyncResult(task_id)
    try:
        # This re-raises a possible TaskError, handled by the error_task_error
        # errorhandler above.
        # Todo: There is no permissions checking in this view, so we shouldn't
        #     have any data in the response. The issue is that the client
        #     needs the URI to the created Annotation (this is not needed in
        #     the other *_wait views). Perhaps do an additional check on
        #     ownership and a possible 403 response?
        annotation.update(serialize(Annotation.query.get(result.get(timeout=3))))
        annotation['ready'] = True
    except TimeoutError:
        annotation['ready'] = False
    return jsonify(annotation=annotation)


@api.route('/data_sources/<int:data_source_id>/annotations', methods=['POST'])
@require_user
@ensure(has_role('admin'), owns_data_source, has_role('annotator'),
        has_role('trader'),
        satisfy=lambda conditions: next(conditions) or (next(conditions) and any(conditions)))
def annotations_add(data_source_id):
    """
    Annotate a data source.

    .. todo:: More parameters for annotation.
    .. todo:: Support other formats than VCF (and check that this is not e.g. a
        BED data source, which of course cannot be annotated).
    """
    # The ``satisfy`` keyword argument used here in the ``ensure`` decorator
    # means that we ensure at least one of:
    # - admin
    # - owns_data_source AND annotator
    # - owns_data_source AND trader

    if 'admin' not in g.user.roles() and 'annotator' not in g.user.roles():
        # This is a trader, so check if the data source has been imported in
        # an active sample.
        if not DataSource.query.get(data_source_id).active:
            raise InvalidDataSource('inactive_data_source', 'Data source '
                'cannot be annotated unless it is imported and active')
    data = request.json or request.form
    result = annotate_vcf.delay(data_source_id, ignore_sample_ids=[])
    log.info('Called task: annotate_vcf(%d) %s', data_source_id, result.task_id)
    uri = url_for('.annotations_wait', task_id=result.task_id)
    # In our unit tests we use CELERY_ALWAYS_EAGER, but in that case we can
    # not get the task result afterwards anymore via .AsyncResult. We know it
    # has been finished directly though, so we just add the resulting
    # annotation to this response, so it can be used in the unit tests.
    # Note that the API thus diverges a bit for the unit tests.
    if current_app.config.get('CELERY_ALWAYS_EAGER'):
        response = jsonify(wait=uri, annotation=serialize(Annotation.query.get(result.result)))
    else:
        response = jsonify(wait=uri)
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
    variant = Variant.query.filter_by(chromosome=chromosome, begin=begin, end=end, reference=reference, variant=alternate).first()
    if variant:
        observations = variant.observations.count()
    else:
        observations = 0
    log.info('Checked variant: chromosome %s, begin %d, end %d, reference %s, alternate %s', chromosome, begin, end, reference, alternate)
    return jsonify(observations=observations)
