"""
REST server views.

Todo: For POST requests, we currently issue a 302 redirect to the view url of
    the created object. An alternative would be to issue 200 success on object
    creation and include the object identifier in a json response body.
    Also, our 302 redirection pages are not json but HTML.
"""


import os
import uuid
from functools import wraps

from flask import abort, request, redirect, url_for, json
from celery.exceptions import TimeoutError

import varda
from varda import app, db
from varda.models import Variant, Sample, Observation, DataSource, Annotation, User
from varda.tasks import TaskError, import_vcf, import_bed, annotate_vcf


def jsonify(_status=None, *args, **kwargs):
    """
    This is a temporary reimplementation of flask.jsonify that accepts a
    special keyword argument '_status' for the HTTP response status code.

    Eventually this will probably be implemented in Flask and we can use
    something like

        >>> @app.route('/')
        >>> def my_view():
        >>>     return flask.jsonify, 404

    See also: https://github.com/mitsuhiko/flask/pull/239
    """
    return app.response_class(json.dumps(dict(*args, **kwargs), indent=None if request.is_xhr else 2),
                              mimetype='application/json', status=_status)


def check_auth(login, password):
    """
    Check if login and password are correct.
    """
    user = User.query.filter_by(login=login).first()
    return user is not None and user.check_password(password)


def require_user(handler, validation=None):
    """
    Todo.
    """
    @wraps(handler)
    def secure_handler(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            abort(401)
        if validation is not None:
            if not validation(user, *args, **kwargs):
                abort(403)
        return handler(*args, **kwargs)
    return secure_handler


class InvalidDataSource(Exception):
    """
    Exception thrown if data source validation failed.
    """
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super(Exception, self).__init__(code, message)

    def to_dict(self):
        return {'code':    self.code,
                'message': self.message}


def validate_data(filename, filetype):
    """
    Peek into the file and determine if it is of the given filetype.
    """
    def validate_bed():
        # Todo.
        pass

    def validate_vcf():
        # Todo.
        pass

    validators = {'bed': validate_bed,
                  'vcf': validate_vcf}
    try:
        validators[filetype]()
    except KeyError:
        raise InvalidDataSource('unknown_filetype', 'Data source filetype is unknown')


@app.errorhandler(400)
def error_bad_request(error):
    return jsonify(error={'code': 'bad_request',
                          'message': 'The request could not be understood due to malformed syntax'},
                   _status=400)


@app.errorhandler(401)
def error_unauthorized(error):
    return jsonify(error={'code': 'unauthorized',
                          'message': 'The request requires user authentication'},
                   _status=401)


@app.errorhandler(403)
def error_forbidden(error):
    return jsonify(error={'code': 'forbidden',
                          'message': 'Not allowed to make this request'},
                   _status=403)


@app.errorhandler(404)
def error_not_found(error):
    return jsonify(error={'code': 'not_found',
                          'message': 'The requested entity could not be found'},
                   _status=404)


@app.errorhandler(413)
def error_entity_too_large(error):
    return jsonify(error={'code': 'entity_too_large',
                          'message': 'The request entity is too large'},
                   _status=413)


@app.errorhandler(TaskError)
def error_task_error(error):
    return jsonify(error=error.to_dict(), _status=500)


@app.errorhandler(InvalidDataSource)
def error_invalid_data_source(error):
    return jsonify(error=error.to_dict(), _status=400)


@app.route('/')
def apiroot():
    return jsonify(api='ok',
                   version=varda.API_VERSION,
                   contact=varda.__contact__)


@app.route('/samples', methods=['GET'])
#@require_user(validation=is_admin)
@require_user
def samples_list():
    """
    curl -i -u pietje:pi3tje http://127.0.0.1:5000/samples
    """
    return jsonify(samples=[s.to_dict() for s in Sample.query])


@app.route('/samples/<sample_id>', methods=['GET'])
def samples_get(sample_id):
    """
    curl -i http://127.0.0.1:5000/samples/2

    Todo: Use <int:sample_id> and check what the error handling of Flask
        will do.
    """
    return jsonify(sample=Sample.query.get_or_404(sample_id).to_dict())


@app.route('/samples', methods=['POST'])
def samples_add():
    """
    curl -i -d 'name=Genome of the Netherlands' -d 'pool_size=500' http://127.0.0.1:5000/samples
    """
    data = request.form
    try:
        name = data['name']
        coverage_threshold = int(data.get('coverage_threshold', 8))
        pool_size = int(data.get('pool_size', 1))
    except (KeyError, ValueError):
        abort(400)
    sample = Sample(name, coverage_threshold, pool_size)
    db.session.add(sample)
    db.session.commit()
    return redirect(url_for('samples_get', sample_id=sample.id))


@app.route('/samples/<sample_id>/observations/wait/<task_id>', methods=['GET'])
def observations_wait(sample_id, task_id):
    """
    Check status of import observations task.

    Note: The sample_id argument is pretty useless here...
    Note: For a non-existing task_id, AsyncResult just returns a result with
        status PENDING.
    """
    result = import_vcf.AsyncResult(task_id)
    try:
        # This re-raises a possible TaskError, handled by the error_task_error
        # errorhandler above.
        result.get(timeout=3)
        ready = True
    except TimeoutError:
        ready = False
    return jsonify(observations={'task_id': task_id, 'ready': ready})


@app.route('/samples/<sample_id>/observations', methods=['POST'])
def observations_add(sample_id):
    """
    curl -i -d 'data_source=3' http://127.0.0.1:5000/samples/1/observations
    """
    data = request.form
    try:
        sample_id = int(sample_id)
        data_source_id = int(data['data_source'])
    except (KeyError, ValueError):
        abort(400)
    Sample.query.get_or_404(sample_id)
    DataSource.query.get_or_404(data_source_id)
    result = import_vcf.delay(sample_id, data_source_id)
    return redirect(url_for('observations_wait', sample_id=sample_id, task_id=result.task_id))


@app.route('/samples/<sample_id>/regions/wait/<task_id>', methods=['GET'])
def regions_wait(sample_id, task_id):
    """
    Check status of import regions task.

    Note: The sample_id argument is pretty useless here...
    """
    result = import_bed.AsyncResult(task_id)
    try:
        # This re-raises a possible TaskError, handled by the error_task_error
        # errorhandler above.
        result.get(timeout=3)
        ready = True
    except TimeoutError:
        ready = False
    return jsonify(regions={'task_id': task_id, 'ready': ready})


@app.route('/samples/<sample_id>/regions', methods=['POST'])
def regions_add(sample_id):
    """
    curl -i -d 'data_source=3' http://127.0.0.1:5000/samples/1/regions
    """
    data = request.form
    try:
        sample_id = int(sample_id)
        data_source_id = int(data['data_source'])
    except (KeyError, ValueError):
        abort(400)
    result = import_bed.delay(sample_id, data_source_id)
    return redirect(url_for('regions_wait', sample_id=sample_id, task_id=result.task_id))


@app.route('/data_sources', methods=['GET'])
def data_sources_list():
    """
    List all uploaded files.
    """
    return jsonify(data_sources=[d.to_dict() for d in DataSource.query])


@app.route('/data_sources/<data_source_id>', methods=['GET'])
def data_sources_get(data_source_id):
    """
    Get an uploaded file id.
    """
    return jsonify(data_source=DataSource.query.get_or_404(data_source_id).to_dict())


@app.route('/data_sources', methods=['POST'])
def data_sources_add():
    """
    Upload VCF or BED file.

    Todo: It might be better to use the mimetype for filetype here instead of
        a separate field.
    """
    try:
        name = request.form['name']
        filetype = request.form['filetype']
        data = request.files['data']
    except KeyError:
        abort(400)
    filename = str(uuid.uuid4())
    filepath = os.path.join(app.config['FILES_DIR'], filename)
    data.save(filepath)
    try:
        validate_data(filepath, filetype)
    except InvalidDataSource:
        os.unlink(filepath)
        raise
    data_source = DataSource(name, filename, filetype)
    db.session.add(data_source)
    db.session.commit()
    return redirect(url_for('data_sources_get', data_source_id=data_source.id))


@app.route('/data_sources/<data_source_id>/annotations', methods=['GET'])
def annotations_list(data_source_id):
    """
    Get annotated versions of a data source.
    """
    return jsonify(annotations=[a.to_dict() for a in DataSource.query.get_or_404(data_source_id).annotations])


@app.route('/data_sources/<data_source_id>/annotations/<annotation_id>', methods=['GET'])
#@require_user #(validation=owns_data_source)
def annotations_get(data_source_id, annotation_id):
    """
    Get annotated version of a data source.

    Todo: The data_source_id argument is kind of useless here...
    Todo: Use flask.send_from_directory
    """
    #return jsonify(annotation=Annotation.query.get_or_404(annotation_id).to_dict())
    a = Annotation.query.get_or_404(annotation_id)
    f = open(os.path.join(app.config['FILES_DIR'], a.filename))
    return f.read()


@app.route('/data_sources/<data_source_id>/annotations/wait/<task_id>', methods=['GET'])
def annotations_wait(data_source_id, task_id):
    """
    Wait for annotated version of a data source.

    Todo: The data_source_id argument is kind of useless here...
    """
    annotation = {'task_id': task_id}
    result = annotate_vcf.AsyncResult(task_id)
    try:
        # This re-raises a possible TaskError, handled by the error_task_error
        # errorhandler above.
        annotation.update({'ready': True, 'id': result.get(timeout=3)})
    except TimeoutError:
        annotation['ready'] = False
    return jsonify(annotation=annotation)


@app.route('/data_sources/<data_source_id>/annotations', methods=['POST'])
def annotations_add(data_source_id):
    """
    Annotate a data source.

    Todo: More parameters for annotation.
    Todo: Support other formats than VCF.
    """
    data = request.form
    try:
        data_source_id = int(data_source_id)
    except ValueError:
        abort(400)
    result = annotate_vcf.delay(data_source_id)
    return redirect(url_for('annotations_wait', data_source_id=data_source_id, task_id=result.task_id))


@app.route('/check_variant', methods=['POST'])
def check_variant():
    """
    Check a variant.

    Todo: Make this a GET request?
    """
    data = request.form
    try:
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
    return jsonify(observations=observations)
