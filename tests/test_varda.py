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


from nose.tools import *

from varda import create_app, db


class TestVarda():
    def setUp(self):
        self.app = create_app()
        ok_(self.app.config.get('TESTING'),
            'Settings do not seem to define your *test* environment!')
        self.client = self.app.test_client()
        # Todo: Start celeryd
        with self.app.test_request_context():
            db.create_all()

    def tearDown(self):
        # Todo: Empty celery, stop celeryd
        with self.app.test_request_context():
            db.drop_all()

    def test_root(self):
        r = self.client.get('/')
        assert 'contact' in r.data
