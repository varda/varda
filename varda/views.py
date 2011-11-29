"""
REST server views.
"""


import os
import uuid

from flask import abort, request, redirect, url_for, jsonify
from celery.exceptions import TimeoutError

import varda
from varda import app, db
from varda.models import Variant, Sample, Observation, DataSource
from varda.tasks import TaskError, import_vcf


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


@app.route('/samples/<id>', methods=['GET'])
def samples_get(id):
    """
    curl -i http://127.0.0.1:5000/samples/2
    """
    return jsonify(sample=Sample.query.get(id).to_dict())


@app.route('/samples', methods=['POST'])
def samples_add():
    """
    curl -i -d 'name=Genome of the Netherlands' -d 'pool_size=500' http://127.0.0.1:5000/samples
    """
    data = request.form
    sample = Sample(data['name'], int(data['coverage_threshold']), int(data['pool_size']))
    db.session.add(sample)
    db.session.commit()
    return redirect(url_for('samples_get', id=sample.id))


@app.route('/samples/<sample_id>/observations', methods=['POST'])
def observations_add(sample_id):
    """
    curl -i -d 'data_source=3' http://127.0.0.1:5000/samples/1/observations
    """
    data = request.form
    result = import_vcf.delay(sample_id, data['data_source'])
    # Todo: check if call could be scheduled by celery
    return redirect(url_for('observations_get', sample_id=sample_id, task_id=result.task_id))


@app.route('/samples/<sample_id>/observations/<task_id>', methods=['GET'])
def observations_get(sample_id, task_id):
    """
    Check status of import observations task.
    """
    result = import_vcf.AsyncResult(task_id)
    try:
        result.get(timeout=1)
    except TaskError as e:
        return jsonify(error=str(e))
    except TimeoutError:
        pass
    return jsonify(observations={'task_id': task_id, 'status': result.status})


@app.route('/data_sources', methods=['GET'])
def data_sources_list():
    """
    List all uploaded files.
    """
    return jsonify(data_sources=[d.to_dict() for d in DataSource.query])


@app.route('/data_sources/<id>', methods=['GET'])
def data_sources_get(id):
    """
    Get an uploaded file id.
    """
    #try:
    #    with open(os.path.join(app.config['FILES_DIR'], data_source.filename)) as file:
    #        data = file.read()
    #except IOError:
    #    abort(404)
    #data_dict = data_source.to_dict()
    #data_dict['data'] = data
    return jsonify(data_source=DataSource.query.get(id).to_dict())


@app.route('/data_sources', methods=['POST'])
def data_sources_add():
    """
    Upload VCF or BED file.
    """
    data = request.files['data']
    if data:
        filename = str(uuid.uuid4())
        data.save(os.path.join(app.config['FILES_DIR'], filename))
        data_source = DataSource(request.form['name'], filename)
        db.session.add(data_source)
        db.session.commit()
        return redirect(url_for('data_sources_get', id=data_source.id))


#@app.route('/populations/<id>', methods=['POST'])
#def merged_observations_add():
#    data = request.form
#    result = add_merged_observations.AsyncResult(id).get(timeout=1.0)
#    # etc


# Below is testing tasks


#@app.route('/cvariants', methods=['POST'])
#def cvariants_add():
#    data = request.form
#    result = add_variant.apply_async( [data[f] for f in ('chromosome', 'begin', 'end', 'reference', 'variant')] )
#    return redirect(url_for('cview', id=result.task_id))


#@app.route('/cview/<id>', methods=['GET'])
#def cview(id):
#    result = add_variant.AsyncResult(id).get(timeout=1.0)
#    return jsonify(variant=result)
