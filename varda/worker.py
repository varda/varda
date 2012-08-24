"""
Helper module for celery to run a worker.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from . import celery, create_app


create_app().app_context().push()
