"""
REST server views.
"""


from flask import jsonify

import varda
from varda import app


@app.route('/info')
def info():
    return jsonify(version=varda.__version__,
                   author=varda.__version__,
                   contact=varda.__contact__,
                   homepage=varda.__homepage__)
