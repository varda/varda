"""
Test Celery tasks.
"""


import tempfile

from flask.ext.testing import TestCase
from nose.tools import *

from varda import create_app, db
from varda.models import User
from varda.tasks import ping


TEST_SETTINGS = {
    'TESTING': True,
    'DATA_DIR': tempfile.mkdtemp(),
    'GENOME': 'tests/data/hg19.fa',
    'REFERENCE_MISMATCH_ABORT': True,
    'SQLALCHEMY_DATABASE_URI': 'sqlite://',
    'BROKER_URL': 'memory://',
    'CELERY_RESULT_BACKEND': 'cache',
    'CELERY_CACHE_BACKEND': 'memory',
    'CELERY_ALWAYS_EAGER': True,
    # Note: If exceptions are propagated, on_failure handlers are not called.
    'CELERY_EAGER_PROPAGATES_EXCEPTIONS': True
}


class TestTasks(TestCase):
    """
    Test Celery tasks, by calling them in various ways.

    .. note:: Since the `flask.ext.testing.TestCase` class is based on
        `unittest.TestCase`, we really need to name our setup and teardown
        methods `setUp` and `tearDown` (note the case). With pure `nose`
        tests this wouldn't be necessary.
    """
    def create_app(self):
        return create_app(TEST_SETTINGS)

    def setUp(self):
        """
        Run once before every test. Setup the test database.
        """
        db.create_all()

    def tearDown(self):
        """
        Run once after every test. Drop the test database.
        """
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
