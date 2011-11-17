"""
REST server views.
"""


from flask import request, redirect, url_for, jsonify

import varda
from varda import app, db
from varda.models import Variant, Population, MergedObservation
from varda.tasks import add_variant


@app.route('/')
def apiroot():
    return jsonify(api='ok',
                   version=varda.API_VERSION,
                   contact=varda.__contact__)


@app.route('/populations', method=['GET'])
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


#@app.route('/populations/<id>', methods=['POST'])
#def merged_observations_add():
#    data = request.form
#    result = add_merged_observations.AsyncResult(id).get(timeout=1.0)
#    # etc


# Below is testing tasks


@app.route('/cvariants', methods=['POST'])
def cvariants_add():
    data = request.form
    result = add_variant.apply_async( [data[f] for f in ('chromosome', 'begin', 'end', 'reference', 'variant')] )
    return redirect(url_for('cview', id=result.task_id))


@app.route('/cview/<id>', methods=['GET'])
def cview(id):
    result = add_variant.AsyncResult(id).get(timeout=1.0)
    return jsonify(variant=result)
