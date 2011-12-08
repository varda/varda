"""
Varda, a variant database interface.
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

__version_info__ = ('1', '0', 'beta-1', 'dev')
__date__ = '16 Nov 2011'


__version__ = '.'.join(__version_info__)
__author__ = 'Leiden University Medical Center'
__contact__ = 'humgen@lumc.nl'
__homepage__ = 'http://www.humgen.nl'


API_VERSION = 1


# Addresses to send errors to
ADMINS = ['m.vermaat.hg@lumc.nl']

# Directory to store uploaded files
FILES_DIR = '/tmp/varda'

# Maximum size for uploaded files
MAX_CONTENT_LENGTH = 1024 * 1024 * 1024  # 1 gigabyte

# Location of server log file
SERVER_LOG_FILE = '/tmp/varda-server.log'

# Location of Celery log file
#CELERYD_LOG_FILE = '/tmp/varda-celeryd.log'

# Todo: Look into this configuration option
#CELERYD_HIJACK_ROOT_LOGGER = False

# Variant database
#SQLALCHEMY_DATABASE_URI = 'mysql://varda:varda@localhost/varda'
SQLALCHEMY_DATABASE_URI = 'postgresql://varda:varda@localhost/varda'

# Celery results
CELERY_RESULT_BACKEND = 'database'
#CELERY_RESULT_DBURI = 'mysql://varda:varda@localhost/vardaresults'
CELERY_RESULT_DBURI = 'postgresql://varda:varda@localhost/vardaresults'

# Celery broker
#BROKER_TRANSPORT = 'sqlalchemy'
#BROKER_HOST = 'mysql://varda:varda@localhost/vardacelery'
#BROKER_HOST = 'postgresql://varda:varda@localhost/vardacelery'
BROKER_URL = 'amqp://varda:varda@localhost:5672/varda'


app = Flask(__name__)
app.config.from_object(__name__)
db = SQLAlchemy(app)
celery = Celery(app)


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


# Views must always be imported last
import varda.views
