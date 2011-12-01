"""
REST server views.

Todo: For POST requests, we currently issue a 302 redirect to the view url of
    the created object. An alternative would be to issue 200 success on object
    creation and include the object identifier in a json response body.
    Also, our 302 redirection pages are not json but HTML.
"""


import os
import uuid

from flask import abort, request, redirect, url_for, json
from celery.exceptions import TimeoutError

import varda
from varda import app, db
from varda.models import Variant, Sample, Observation, DataSource
from varda.tasks import TaskError, import_vcf, import_bed


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


@app.errorhandler(400)
def error_not_found(error):
    return jsonify(error={'code': 'bad_request',
                          'message': 'The request could not be understood due to malformed syntax'},
                   _status=400)


@app.errorhandler(404)
def error_not_found(error):
    return jsonify(error={'code': 'not_found',
                          'message': 'The requested entity could not be found'},
                   _status=404)


@app.errorhandler(TaskError)
def error_task_error(error):
    return jsonify(error=error.to_dict(), _status=500)


@app.route('/')
def apiroot():
    return jsonify(api='ok',
                   version=varda.API_VERSION,
                   contact=varda.__contact__)


@app.route('/samples', methods=['GET'])
def samples_list():
    """
    curl -i http://127.0.0.1:5000/samples
    """
    return jsonify(samples=[s.to_dict() for s in Sample.query])


@app.route('/samples/<sample_id>', methods=['GET'])
def samples_get(sample_id):
    """
    curl -i http://127.0.0.1:5000/samples/2
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
    except (IndexError, ValueError):
        abort(400)
    sample = Sample(name, coverage_threshold, pool_size)
    db.session.add(sample)
    db.session.commit()
    return redirect(url_for('samples_get', id=sample.id))


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
    except (IndexError, ValueError):
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
    except (IndexError, ValueError):
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
    """
    try:
        name = request.form['name']
        data = request.files['data']
    except IndexError:
        abort(400)
    filename = str(uuid.uuid4())
    data.save(os.path.join(app.config['FILES_DIR'], filename))
    data_source = DataSource(name, filename)
    db.session.add(data_source)
    db.session.commit()
    return redirect(url_for('data_sources_get', id=data_source.id))
