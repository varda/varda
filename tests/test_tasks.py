"""
Test Celery tasks.
"""


import tempfile

from nose.tools import *

from varda import create_app, db
from varda.models import User
from varda.tasks import ping


TEST_SETTINGS = {
    'TESTING': True,
    'FILES_DIR': tempfile.mkdtemp(),
    'SQLALCHEMY_DATABASE_URI': 'sqlite://',
    'BROKER_TRANSPORT': 'memory',
    'CELERY_ALWAYS_EAGER': True,
    'CELERY_EAGER_PROPAGATES_EXCEPTIONS': False
}


class TestTasks():
    """
    Test Celery tasks, by calling them in various ways.
    """
    def setup(self):
        """
        Run once before every test. Setup the test database.
        """
        self.app = create_app(TEST_SETTINGS)
        self.client = self.app.test_client()
        with self.app.test_request_context():
            db.create_all()
            user = User('Test User', 'test', 'test', roles=['admin'])
            db.session.add(user)
            db.session.commit()

    def teardown(self):
        """
        Run once after every test. Drop the test database.
        """
        with self.app.test_request_context():
            db.session.remove()
            db.drop_all()

    def test_ping_blocking(self):
        """
        Synchronously execute a task and get the result.
        """
        assert_equal(ping.apply().result, 'pong')

    def test_ping_delayed(self):
        """
        Asynchronously execute a task and get the result.

        This works, because we set CELERY_ALWAYS_EAGER to True in the test
        environment.
        """
        assert_equal(ping.delay().result, 'pong')
