"""
Varda, a database for genomic variation frequencies.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from celery import Celery
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy


from .genome import Genome


# We follow a versioning scheme compatible with setuptools [1] where the
# package version is always that of the upcoming release (and not that of the
# previous release), post-fixed with ``.dev``. Only in a release commit, the
# ``.dev`` is removed (and added again in the next commit).
#
# Note that this scheme is not 100% compatible with SemVer [2] which would
# require ``-dev`` instead of ``.dev``.
#
# [1] http://peak.telecommunity.com/DevCenter/setuptools#specifying-your-project-s-version
# [2] http://semver.org/


__version_info__ = ('0', '1', '0', 'dev')
__date__ = '10 Feb Nov 2012'


__version__ = '.'.join(__version_info__)
__author__ = 'Martijn Vermaat'
__contact__ = 'martijn@vermaat.name'
__homepage__ = 'http://martijn.vermaat.name'


db = SQLAlchemy()
celery = Celery('varda')
genome = Genome()


def create_app(settings=None):
    """
    Create a Flask instance for Varda. Configuration settings are read from a
    file specified by the ``VARDA_SETTINGS`` environment variable, if it
    exists.

    :arg settings: Dictionary of configuration settings. These take precedence
        over settings read from the file pointed to by the ``VARDA_SETTINGS``
        environment variable.
    :type settings: dict

    :return: Flask application instance.
    """
    app = Flask('varda')
    app.config.from_object('varda.default_settings')
    app.config.from_envvar('VARDA_SETTINGS', silent=True)
    # Todo: Print a warning if no configuration other than the default is in
    #     use.
    if settings:
        app.config.update(settings)
    db.init_app(app)
    celery.conf.add_defaults(app.config)
    if app.config['GENOME'] is not None:
        genome.init(app.config['GENOME'])
    from .api import api
    app.register_blueprint(api, url_prefix=app.config['API_URL_PREFIX'])
    if app.config['AULE_LOCAL_PATH'] is not None:
        assert (app.config['API_URL_PREFIX'] !=
                app.config['AULE_URL_PREFIX'])
        from .web import web
        app.register_blueprint(web,
                               url_prefix=app.config['AULE_URL_PREFIX'])
    return app
