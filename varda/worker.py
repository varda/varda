"""
Helper module for celery to run a worker.

Copyright (c) 2012, Leiden University Medical Center <humgen@lumc.nl>
Copyright (c) 2012, Martijn Vermaat <martijn@vermaat.name>

Licensed under the MIT license, see the LICENSE file.
"""


from varda import create_app, celery


create_app()
