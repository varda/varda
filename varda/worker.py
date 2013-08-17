"""
Helper module for celery to run a worker.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from . import celery, create_app


# Todo: Should we make it possible to use create_reverse_proxied_app here?
create_app().app_context().push()
