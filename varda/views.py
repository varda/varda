"""
REST server views.
"""


from flask import request, redirect, url_for, jsonify

import varda
from varda import app, db
from varda.models import Variant
from varda.tasks import add_three, add_variant


@app.route('/')
def apiroot():
    return jsonify(api='ok',
                   version=varda.API_VERSION,
                   contact=varda.__contact__)


@app.route('/variants', methods=['GET'])
def variants_list():
    return jsonify(variants=[v.to_dict() for v in Variant.query])


@app.route('/variants/<id>', methods=['GET'])
def variants_get(id):
    return jsonify(variant=Variant.query.get(id).to_dict())


@app.route('/variants', methods=['POST'])
def variants_add():
    data = request.form
    variant = Variant(data['chromosome'],
                      data['begin'],
                      data['end'],
                      data['reference'],
                      data['variant'])
    db.session.add(variant)
    db.session.commit()
    return redirect(url_for('variants_get', id=variant.id))


@app.route('/addthree', methods=['POST'])
def addthree():
    data = request.form
    result = add_three.apply_async( (int(data['number']),) )
    return redirect(url_for('view', id=result.task_id))


@app.route('/view/<id>', methods=['GET'])
def view(id):
    result = add_three.AsyncResult(id).get(timeout=1.0)
    return jsonify(number=result)


@app.route('/cvariants', methods=['POST'])
def cvariants_add():
    data = request.form
    result = add_variant.apply_async( [data[f] for f in ('chromosome', 'begin', 'end', 'reference', 'variant')] )
    return redirect(url_for('cview', id=result.task_id))


@app.route('/cview/<id>', methods=['GET'])
def cview(id):
    result = add_variant.AsyncResult(id).get(timeout=1.0)
    return jsonify(variant=result)
