"""
Varda server, a database for genomic variantion.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from celery import Celery
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy


from .genome import Genome


# On the event of a new release, we update the __version_info__ and __date__
# package globals and set RELEASE to True.
# Before a release, a development version is denoted by a __version_info__
# ending with a 'dev' item. Also, RELEASE is set to False (indicating that
# the __date__ value is to be ignored).
#
# We follow a versioning scheme compatible with setuptools [1] where the
# __version_info__ variable always contains the version of the upcomming
# release (and not that of the previous release), post-fixed with a 'dev'
# item. Only in a release commit, this 'dev' item is removed (and added
# again in the next commit).
#
# [1] http://peak.telecommunity.com/DevCenter/setuptools#specifying-your-project-s-version

RELEASE = False

__version_info__ = ('0', '1', 'dev')
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
    Create a Flask instance for Varda server. Configuration settings are read
    from a file specified by the ``VARDA_SETTINGS`` environment variable, if
    it exists.

    :arg settings: Dictionary of configuration settings. These take precedence
        over settings read from the file pointed to by the ``VARDA_SETTINGS``
        environment variable.
    :type settings: dict

    :return: Flask application instance.
    """
    app = Flask('varda')
    app.config.from_object('varda.default_settings')
    app.config.from_envvar('VARDA_SETTINGS', silent=True)
    if settings:
        app.config.update(settings)
    db.init_app(app)
    celery.conf.add_defaults(app.config)
    if app.config['GENOME'] is not None:
        genome.init(app.config['GENOME'])
    from .api import api
    app.register_blueprint(api, url_prefix=app.config['API_URL_PREFIX'])
    if app.config['VARDA_WEB_LOCAL_PATH'] is not None:
        assert (app.config['API_URL_PREFIX'] !=
                app.config['VARDA_WEB_URL_PREFIX'])
        from .web import web
        app.register_blueprint(web,
                               url_prefix=app.config['VARDA_WEB_URL_PREFIX'])
    return app
