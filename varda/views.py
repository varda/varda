"""
REST server views.
"""


from flask import request, redirect, url_for, jsonify

import varda
from varda import app, db
from varda.models import Variant


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
