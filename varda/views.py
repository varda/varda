"""
REST server views.
"""


import os
import uuid

from flask import abort, request, redirect, url_for, jsonify

import varda
from varda import app, db
from varda.models import Variant, Population, MergedObservation
from varda.tasks import import_merged_vcf


@app.route('/')
def apiroot():
    return jsonify(api='ok',
                   version=varda.API_VERSION,
                   contact=varda.__contact__)


@app.route('/populations', methods=['GET'])
def populations_list():
    """
    curl -i http://127.0.0.1:5000/populations
    """
    return jsonify(populations=[p.to_dict() for p in Population.query])


@app.route('/populations/<id>', methods=['GET'])
def populations_get(id):
    """
    curl -i http://127.0.0.1:5000/populations/2
    """
    return jsonify(population=Population.query.get(id).to_dict())


@app.route('/populations', methods=['POST'])
def populations_add():
    """
    curl -i -d 'name=Genome of the Netherlands' -d 'size=500' http://127.0.0.1:5000/populations
    """
    data = request.form
    population = Population(data['name'], int(data['size']))
    db.session.add(population)
    db.session.commit()
    return redirect(url_for('populations_get', id=population.id))


@app.route('/populations/<population_id>/observations', methods=['POST'])
def merged_observations_add(population_id):
    """
    curl -i -d 'file=296748de-44ed-4e53-904f-80d181aaaa53' http://127.0.0.1:5000/populations/1/observations
    """
    data = request.form
    #population = Population.query.get(id)
    result = import_merged_vcf.apply_async( [population_id, os.path.join(app.config['FILES_DIR'], data['file'])] )
    # Todo: check if call could be scheduled by celery
    return redirect(url_for('populations_get', id=population_id))


@app.route('/files', methods=['GET'])
def files_list():
    """
    List all uploaded files.
    """
    return jsonify(files=map(lambda id: {'id': id},
                             filter(lambda id: os.path.isfile(os.path.join(app.config['FILES_DIR'], id)),
                                    os.listdir(app.config['FILES_DIR']))))


@app.route('/files/<id>', methods=['GET'])
def files_get(id):
    """
    Get an uploaded file id.
    """
    try:
        with open(os.path.join(app.config['FILES_DIR'], id)) as file:
            data = file.read()
    except IOError:
        abort(404)
    return jsonify(file={'id': id, 'data': data})


@app.route('/files', methods=['POST'])
def files_add():
    """
    Upload VCF file.
    """
    file = request.files['file']
    if file:
        id = str(uuid.uuid4())
        file.save(os.path.join(app.config['FILES_DIR'], id))
        return redirect(url_for('files_get', id=id))


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
