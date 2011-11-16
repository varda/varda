"""
REST server views.
"""


from varda import app


@app.route('/')
def index():
    return 'Hello World!'
