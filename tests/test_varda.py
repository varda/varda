"""
Varda unit tests.

To make sure we have a test database with test user, run this once:

    createuser --pwprompt --encrypted --no-adduser --no-createdb --no-createrole vardatest
    createdb --encoding=UNICODE --owner=vardatest vardatest
    createdb --encoding=UNICODE --owner=vardatest vardatestresults

    sudo rabbitmqctl add_user vardatest vardatest
    sudo rabbitmqctl add_vhost vardatest
    sudo rabbitmqctl set_permissions -p vardatest vardatest '.*' '.*' '.*'
"""


import os
import tempfile
from nose.tools import *
from varda import app, db


TESTING = True
FILES_DIR = tempfile.mkdtemp()
SQLALCHEMY_DATABASE_URI = 'postgresql://vardatest:vardatest@localhost/vardatest'
CELERY_RESULT_BACKEND = 'database'
CELERY_RESULT_DBURI = 'postgresql://vardatest:vardatest@localhost/vardatestresults'
BROKER_URL = 'amqp://vardatest:vardatest@localhost:5672/vardatest'


class TestVarda():
    def setUp(self):
        # Todo: This doesn't work, the db should be created after setting the
        # config. Probably requires some refactoring in varda/__init__.py.
        app.config.from_object(__name__)
        self.app = app.test_client()
        # Todo: Start celeryd
        db.create_all()

    def tearDown(self):
        db.drop_all()
        # Todo: Empty celery, stop celeryd
        # Todo: Maybe delete tempdir

    def test_root(self):
        r = self.app.get('/')
        assert 'contact' in r.data
