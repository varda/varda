"""
Varda unit tests.

The tests assume there is a PostgreSQL server running on localhost with a
database 'vardatest' accessibly for the user 'vardatest' with password
'vardatest'.

Run these commands once to set this up:

    createuser --pwprompt --encrypted --no-adduser --no-createdb --no-createrole vardatest
    createdb --encoding=UNICODE --owner=vardatest vardatest

Alternatively, you can change the configuration settings below.
"""


import time
import tempfile

from nose.tools import *

from varda import create_app, db
from varda.tasks import ping


TEST_SETTINGS = {
    'TESTING': True,
    'FILES_DIR': tempfile.mkdtemp(),
    'SQLALCHEMY_DATABASE_URI': 'postgresql://vardatest:vardatest@localhost/vardatest',
    'BROKER_TRANSPORT': 'memory',
    'CELERY_ALWAYS_EAGER': True,
    'CELERY_EAGER_PROPAGATES_EXCEPTIONS': True
}


class TestVarda():
    def setUp(self):
        self.app = create_app(TEST_SETTINGS)
        self.client = self.app.test_client()
        with self.app.test_request_context():
            db.create_all()

    def tearDown(self):
        with self.app.test_request_context():
            db.drop_all()

    def test_root(self):
        r = self.client.get('/')
        assert 'contact' in r.data

    def test_ping_blocking(self):
        r = ping.apply()
        assert_equal(r.result, 'pong')

    def test_ping_delayed(self):
        r = ping.delay()
        time.sleep(1)
        assert_equal(r.result, 'pong')
