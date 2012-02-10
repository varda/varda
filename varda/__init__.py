"""
Varda, a variant database interface.

Copyright (c) 2011-2012, Leiden University Medical Center <humgen@lumc.nl>
Copyright (c) 2011-2012, Martijn Vermaat <martijn@vermaat.name>

Licensed under the MIT license, see the LICENSE file.
"""


from flask import Flask
from flaskext.sqlalchemy import SQLAlchemy
from flask_celery import Celery


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
__author__ = 'Leiden University Medical Center'
__contact__ = 'humgen@lumc.nl'
__homepage__ = 'http://www.humgen.nl'


API_VERSION = 1


db = SQLAlchemy()
celery = Celery()


def create_app():
    app = Flask(__name__)
    app.config.from_object('varda.default_settings')
    app.config.from_envvar('VARDA_SETTINGS', silent=True)
    db.init_app(app)
    celery.init_app(app)
    from varda.views import api
    app.register_blueprint(api)
    return app


# Todo: The following needs refactoring since we use a create_app function.
temp = '''
# In production, send server errors to admins and log warnings to a file
if not app.debug:
    import logging
    from logging import FileHandler, getLogger, Formatter
    from logging.handlers import SMTPHandler
    mail_handler = SMTPHandler('127.0.0.1', 'm.vermaat.hg@lumc.nl', ADMINS,
                               'Varda Server Error')
    mail_handler.setLevel(logging.ERROR)
    mail_handler.setFormatter(Formatter("""
Message type:       %(levelname)s
Location:           %(pathname)s:%(lineno)d
Module:             %(module)s
Function:           %(funcName)s
Time:               %(asctime)s

Message:

%(message)s
"""))
    file_handler = FileHandler(SERVER_LOG_FILE)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(Formatter('%(asctime)s %(levelname)s: %(message)s'))
    loggers = [app.logger, getLogger('sqlalchemy'), getLogger('celery')]
    for logger in loggers:
        app.logger.addHandler(mail_handler)
        app.logger.addHandler(file_handler)
'''
