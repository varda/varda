"""
REST server views.

Todo: Representations of resources can sometimes be nested arbitrarily deeply.
    One extreme would be to only represent nested resources by their URL, the
    other extreme would be to always give the full JSON representation of the
    nested resource (unless the nesting is infinitely deep of course). A
    possible solution is to add a ?depth=N query parameter to view URLs, where
    N would be how deep to expand URLs with JSON representations. A nice
    implementation for this on the server side will require some thinking...
    Also see [1].
Todo: Use caching headers whenever we can. ETag headers are good when you can
    easily reduce a resource to a hash value. Last-Modified should indicate to
    you that keeping around a timestamp of when resources are updated is a
    good idea. Cache-Control and Expires should be given sensible values.
Todo: Implement pagination for collection representations, perhaps with HTTP
    range headers. This is related to sorting and filtering. See e.g. [3].
Todo: Use accept HTTP headers.
Todo: Correctly use HTTP verbs, see [2].

[1] http://news.ycombinator.com/item?id=3491227
[2] http://news.ycombinator.com/item?id=3514668
[3] http://dojotoolkit.org/reference-guide/quickstart/rest.html

Copyright (c) 2011-2012, Leiden University Medical Center <humgen@lumc.nl>
Copyright (c) 2011-2012, Martijn Vermaat <martijn@vermaat.name>

Licensed under the MIT license, see the LICENSE file.
"""


import os
import uuid
from functools import wraps

from flask import Blueprint, current_app, g, abort, request, redirect, url_for, jsonify, send_from_directory
from celery.exceptions import TimeoutError

import varda
from varda import db, log
from varda.models import InvalidDataSource, Variant, Sample, Observation, DataSource, Annotation, User
from varda.tasks import TaskError, import_vcf, import_bed, annotate_vcf


api = Blueprint('api', __name__)


# Dispatch table for the represent function below
_representers = []


def represents(model):
    """
    Decorator to specify that a function creates a representation for a
    certain model.
    """
    def represents_model(representer):
        _representers.append( (model, representer) )
        @wraps(representer)
        def wrapped_representer(*args, **kwargs):
            return representer(*args, **kwargs)
        return wrapped_representer
    return represents_model


@represents(User)
def represent_user(object):
    """
    Create a RESTfull representation of a user as dictionary.
    """
    return {'uri':   url_for('.users_get', login=object.login),
            'name':  object.name,
            'login': object.login,
            'roles': list(object.roles()),
            'added': str(object.added)}


@represents(DataSource)
def represent_data_source(object):
    """
    Create a RESTfull representation of a data source as dictionary.
    """
    return {'uri':         url_for('.data_sources_get', data_source_id=object.id),
            'user':        url_for('.users_get', login=object.user.login),
            'annotations': url_for('.annotations_list', data_source_id=object.id),
            'name':        object.name,
            'filetype':    object.filetype,
            'gzipped':     object.gzipped,
            'added':       str(object.added)}


@represents(Annotation)
def represent_annotation(object):
    """
    Create a RESTfull representation of an annotation as dictionary.
    """
    return {'uri':         url_for('.annotations_get', data_source_id=object.data_source_id, annotation_id=object.id),
            'data_source': url_for('.data_sources_get', data_source_id=object.data_source_id),
            'gzipped':     object.data_source.gzipped,
            'added':       str(object.added)}


@represents(Sample)
def represent_sample(object):
    """
    Create a RESTfull representation of a sample as dictionary.
    """
    return {'uri':                url_for('.samples_get', sample_id=object.id),
            'user':               url_for('.users_get', login=object.user.login),
            'observations':       url_for('.observations_add', sample_id=object.id),
            'regions':            url_for('.regions_add', sample_id=object.id),
            'name':               object.name,
            'coverage_threshold': object.coverage_threshold,
            'pool_size':          object.pool_size,
            'added':              str(object.added)}


@represents(InvalidDataSource)
@represents(TaskError)
def represent_exception(object):
    """
    Create a RESTfull representation of an exception as dictionary.
    """
    return {'code':    object.code,
            'message': object.message}


#@represents(Variant)
#def represent_variant(object):
#    return {'id':         object.id,
#            'chromosome': object.chromosome,
#            'begin':      object.begin,
#            'end':        object.end,
#            'reference':  object.reference,
#            'variant':    object.variant}
#@represents(Observation)
#def represent_observation(object):
#    return {'sample':           object.sample.id,
#            'variant':          object.variant.id,
#            'data_source':      object.data_source.id,
#            'total_coverage':   object.total_coverage,
#            'variant_coverage': object.variant_coverage,
#            'support':          object.support}
#@represents(Region)
#def represent_region(object):
#    return {'sample':      object.sample.id,
#            'data_source': object.data_source.id,
#            'chromosome':  object.chromosome,
#            'begin':       object.begin,
#            'end':         object.end}


def represent(object):
    """
    Create a RESTfull representation of an object as dictionary.

    This function dispatches to a specific representer function depending on
    the type of object at hand.

    Note: Returns None if no representer was found.
    Note: I don't think this construction of creating representations is
        especially elegant, but it gets the job done and I really don't want
        any functionality for representations in the models themselves.
    """
    for model, representer in _representers:
        if isinstance(object, model):
            return representer(object)


def get_user(login, password):
    """
    Check if login and password are correct and return the user if so, else
    return None.
    """
    user = User.query.filter_by(login=login).first()
    if user is not None and user.check_password(password):
        return user


def require_user(rule):
    """
    Decorator for user authentication.

    The app.route decorator should always be first, for example:

        >>> @app.route('/samples/<sample_id>', methods=['GET'])
        >>> @require_user
        >>> def get_sample(sample_id):
        ...     return 'sample'

    If authentication was successful, the authenticated user instance can be
    accessed through g.user. Otherwise, the request is aborted with a 401
    response code.
    """
    @wraps(rule)
    def secure_rule(*args, **kwargs):
        if g.user is None:
            abort(401)
        return rule(*args, **kwargs)
    return secure_rule


def ensure(*conditions, **options):
    """
    Decorator to ensure some given conditions are met.

    The conditions arguments are functions returning True on success and False
    otherwise. By default, all conditions must be met. A custom scheme can be
    specified with the satisfy keyword argument, which must be a function
    consuming an iterable and returning a boolean. For example, satisfy=any
    uses the standard library function any to ensure that at least one of the
    conditions is met.

    Typical conditions may depend on the authorized user. In that case, use
    the require_user decorator first, for example:

        >>> def is_admin():
        ...     return 'admin' in g.user.roles()
        ...
        >>> @app.route('/samples', methods=['GET'])
        >>> @require_user
        >>> ensure(is_admin)
        >>> def list_variants():
        ...     return []

    To specify which keyword arguments to pass to the condition functions as
    positional and keyword arguments, use the args and kwargs keyword
    arguments, respectively.

    The args keyword argument lists the rule keyword arguments by name that
    should be passed as positional arguments to the condition functions, in
    that order. For example, to pass the 'variant_id' argument:

        >>> def owns_variant(variant):
        ...     return True
        ...
        >>> @app.route('/samples/<sample_id>/variants/<variant_id>', methods=['GET'])
        >>> @require_user
        >>> ensure(owns_variant, args=['variant_id'])
        >>> def get_variant(sample_id, variant_id):
        ...     return 'variant'

    The kwargs keyword argument maps condition function keyword arguments to
    their respective rule keyword arguments. For example, to pass the
    'sample_id' and 'variant_id' rule arguments as 'sample' and 'variant'
    keyword arguments to the condition functions:

        >>> def owns_sample_and_variant(variant=None, sample=None):
        ...     return True
        ...
        >>> @app.route('/samples/<sample_id>/variants/<variant_id>', methods=['GET'])
        >>> @require_user
        >>> ensure(owns_sample_and_variant, kwargs={'sample': 'sample_id', 'variant': 'variant_id'})
        >>> def get_variant(sample_id, variant_id):
        ...     return 'variant'

    By default, the condition functions are passed all rule keyword arguments.
    This makes it easy to use conditions that use the same names for keyword
    arguments as the decorated rule without the need for the args or kwargs
    arguments:

        >>> def owns_variant(variant_id, **_):
        ...     return True
        ...
        >>> @app.route('/samples/<sample_id>/variants/<variant_id>', methods=['GET'])
        >>> @require_user
        >>> ensure(owns_variant)
        >>> def get_variant(sample_id, variant_id):
        ...     return 'variant'

    Note that since all keyword arguments are passed here, the condition
    function has to accept all of them and not just the one it uses. The
    pattern **_ as shown here captures any additional keyword arguments. If
    you want to explicitely don't pass any keyword arguments, use kwargs={}.

    Finally, an example with multiple conditions where at least one of them
    must be met:

        >>> @app.route('/samples/<sample_id>', methods=['GET'])
        >>> @require_user
        >>> @ensure(is_admin, owns_sample, satisfy=any)
        >>> def get_samples(sample_id):
        ...     return 'variant'

    Note: The main limitation here is that only one argument scheme can be
        given, which is used for all condition functions. Therefore it is
        useful to have consistent argument naming in your condition functions.
    """
    satisfy = options.pop('satisfy', all)
    args = options.pop('args', [])
    kwargs = options.pop('kwargs', None)

    def ensure_conditions(rule):
        @wraps(rule)
        def ensured_rule(*rule_args, **rule_kwargs):
            condition_args = [rule_kwargs.get(arg) for arg in args]
            if kwargs is None:
                condition_kwargs = rule_kwargs
            else:
                condition_kwargs = {name: rule_kwargs.get(value)
                                    for name, value in kwargs.items()}
            if not satisfy(c(*condition_args, **condition_kwargs)
                           for c in conditions):
                abort(403)
            return rule(*rule_args, **rule_kwargs)
        return ensured_rule

    return ensure_conditions


def has_role(role):
    """
    Given a role, return a function that can be used as a condition argument
    for the ensure decorator.

    Example:

        >>> @app.route('/samples', methods=['GET'])
        >>> @require_user
        >>> ensure(has_role('admin'))
        >>> def list_variants():
        ...     return []

    The resulting condition returns True if there is an authenticated user and
    it has the requested role, False otherwise.

    Note: We add the keyword arguments wildcard **_ so this function can be
        easily used as condition argument to the ensure decorator even if
        there are unrelated keyword arguments for the decorated rule.
    """
    def condition(**_):
        return g.user is not None and role in g.user.roles()
    return condition


def owns_sample(sample_id, **_):
    """
    Note: We add the keyword arguments wildcard **_ so this function can be
        easily used as condition argument to the ensure decorator even if
        there are unrelated keyword arguments for the decorated rule.
    """
    sample = Sample.query.get(sample_id)
    return sample is not None and sample.user is g.user


def owns_data_source(data_source_id, **_):
    """
    Note: We add the keyword arguments wildcard **_ so this function can be
        easily used as condition argument to the ensure decorator even if
        there are unrelated keyword arguments for the decorated rule.
    """
    data_source = DataSource.query.get(data_source_id)
    return data_source is not None and data_source.user is g.user


def has_login(login, **_):
    """
    Note: We add the keyword arguments wildcard **_ so this function can be
        easily used as condition argument to the ensure decorator even if
        there are unrelated keyword arguments for the decorated rule.
    """
    return g.user.login == login


@api.before_request
def before_request():
    """
    Make sure we add a User instance to the global objects if we have
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
    return jsonify(error=represent(error)), 500


@api.errorhandler(InvalidDataSource)
def error_invalid_data_source(error):
    return jsonify(error=represent(error)), 400


@api.route('/')
def apiroot():
    api = {'status':  'ok',
           'version': varda.API_VERSION,
           'contact': varda.__contact__,
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
        authentication.update(authenticated=True, user=represent(g.user))
    return jsonify(authentication=authentication)


@api.route('/users', methods=['GET'])
@require_user
@ensure(has_role('admin'))
def users_list():
    """
    curl -i -u pietje:pi3tje http://127.0.0.1:5000/users
    """
    return jsonify(users=[represent(u) for u in User.query])


@api.route('/users/<login>', methods=['GET'])
@require_user
@ensure(has_role('admin'), has_login, satisfy=any)
def users_get(login):
    """
    curl -i http://127.0.0.1:5000/users/pietje
    """
    user = User.query.filter_by(login=login).first()
    if user is None:
        abort(404)
    return jsonify(user=represent(user))


@api.route('/users', methods=['POST'])
@require_user
@ensure(has_role('admin'))
def users_add():
    """
    Roles must be listed in a string separated by a comma.

    Todo: Check for duplicate login.
    Todo: Optionally generate password.
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
    curl -i -u pietje:pi3tje http://127.0.0.1:5000/samples
    """
    return jsonify(samples=[represent(s) for s in Sample.query])


@api.route('/samples/<int:sample_id>', methods=['GET'])
@require_user
@ensure(has_role('admin'), owns_sample, satisfy=any)
def samples_get(sample_id):
    """
    curl -i http://127.0.0.1:5000/samples/2
    """
    return jsonify(sample=represent(Sample.query.get_or_404(sample_id)))


@api.route('/samples', methods=['POST'])
@require_user
@ensure(has_role('admin'), has_role('importer'), satisfy=any)
def samples_add():
    """
    curl -i -d 'name=Genome of the Netherlands' -d 'pool_size=500' http://127.0.0.1:5000/samples
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


@api.route('/observations/wait/<task_id>', methods=['GET'])
@require_user
def observations_wait(task_id):
    """
    Check status of import observations task.

    Todo: Merge with other *_wait functions.

    Note: For a non-existing task_id, AsyncResult just returns a result with
        status PENDING.
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
    curl -i -d 'data_source=/data_sources/3' http://127.0.0.1:5000/samples/1/observations
    """
    data = request.json or request.form
    try:
        sample_id = int(sample_id)
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

    Todo: Merge with other *_wait functions.
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
    curl -i -d 'data_source=3' http://127.0.0.1:5000/samples/1/regions
    """
    data = request.json or request.form
    try:
        sample_id = int(sample_id)
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
    return jsonify(data_sources=[represent(d) for d in DataSource.query])


@api.route('/data_sources/<int:data_source_id>', methods=['GET'])
@require_user
@ensure(has_role('admin'), owns_data_source, satisfy=any)
def data_sources_get(data_source_id):
    """
    Get an uploaded file id.
    """
    return jsonify(data_source=represent(DataSource.query.get_or_404(data_source_id)))


@api.route('/data_sources', methods=['POST'])
@require_user
def data_sources_add():
    """
    Upload VCF or BED file.

    Todo: It might be better to use the mimetype for filetype here instead of
        a separate field.
    Todo: Have an option to add data source by external url instead of upload.
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
    return jsonify(annotations=[represent(a) for a in DataSource.query.get_or_404(data_source_id).annotations])


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

    Todo: Merge with other *_wait functions.
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
        annotation.update(represent(Annotation.query.get(result.get(timeout=3))))
        annotation['ready'] = True
    except TimeoutError:
        annotation['ready'] = False
    return jsonify(annotation=annotation)


@api.route('/data_sources/<int:data_source_id>/annotations', methods=['POST'])
@require_user
@ensure(has_role('admin'), has_role('annotator'), owns_data_source,
        satisfy=lambda conditions: next(conditions) or all(conditions))
def annotations_add(data_source_id):
    """
    Annotate a data source.

    Note: The satisfy keyword argument used here in the ensure decorator means
        that we ensure: admin OR (annotator AND owns_data_source).

    Todo: More parameters for annotation.
    Todo: Support other formats than VCF (and check that this is not e.g. a
        BED data source, which of course cannot be annotated).
    Todo: Only permit annotation if the data source is imported.
    """
    data = request.json or request.form
    try:
        data_source_id = int(data_source_id)
    except ValueError:
        abort(400)
    result = annotate_vcf.delay(data_source_id, ignore_sample_ids=[])
    log.info('Called task: annotate_vcf(%d) %s', data_source_id, result.task_id)
    uri = url_for('.annotations_wait', task_id=result.task_id)
    # In our unit tests we use CELERY_ALWAYS_EAGER, but in that case we can
    # not get the task result afterwards anymore via .AsyncResult. We know it
    # has been finished directly though, so we just add the resulting
    # annotation to this response, so it can be used in the unit tests.
    # Note that the API thus diverges a bit for the unit tests.
    if current_app.config.get('CELERY_ALWAYS_EAGER'):
        response = jsonify(wait=uri, annotation=represent(Annotation.query.get(result.result)))
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

    Todo: Make this a GET request?

    We also want to check frequencies. For example:

        SELECT COUNT(*) FROM Observation, Sample
        WHERE Observation.sampleId = Sample.id
        AND Observation.variantId = %i
        AND Sample.id > 100
        AND Sample.id NOT IN (%s)

    will be something like:

        Observation.query.join(Sample).filter(Observation.variant_id == 1).\
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
