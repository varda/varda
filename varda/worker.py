"""
Helper module for celery to run a worker.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from celery.signals import worker_process_init

from . import create_app, genome


@worker_process_init.connect
def init_genome(**kwargs):
    # Duplicate the open file object of the reference genome. This is needed
    # because file descriptors are inherited after fork, and thus shared
    # between worker processes, causing race conditions with seek and read.
    f = genome.faidx.file
    genome.faidx.file = open(f.name, f.mode)


# Todo: Should we make it possible to use create_reverse_proxied_app here?
create_app().app_context().push()


from . import celery  # noqa
