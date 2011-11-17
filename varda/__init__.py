"""
Varda, a variant database interface.
"""


from flask import Flask
from flaskext.sqlalchemy import SQLAlchemy
from flaskext.celery import Celery


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

SQLALCHEMY_DATABASE_URI = 'mysql://varda:varda@localhost/varda'

CELERY_RESULT_BACKEND = 'database'
CELERY_RESULT_DBURI = 'mysql://varda:varda@localhost/vardaresults'

BROKER_TRANSPORT = 'sqlalchemy'
BROKER_HOST = 'mysql://varda:varda@localhost/vardacelery'


#def create_app():
#    return Flask(__name__)


app = Flask(__name__)
app.config.from_object(__name__)
db = SQLAlchemy(app)
celery = Celery(app)


import varda.views
