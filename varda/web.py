"""
Varda web.

This is used if the configuration setting `VARDA_WEB` is set. The REST API is
then mounted under the ``/api`` path and the server root serves the Varda web
client application from the `VARDA_WEB` directory.

This is useful during local development, since Varda web and Varda server must
share the same domain by the browser's same-origin policy.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


import os.path

from flask import Blueprint, current_app, send_from_directory


web = Blueprint('web', __name__)


@web.route('/')
@web.route('/<path:filename>')
def varda_web(filename=None):
    path = current_app.config['VARDA_WEB']
    if not filename or not os.path.isfile(os.path.join(path, filename)):
        filename = 'varda.html'
    return send_from_directory(path, filename)
