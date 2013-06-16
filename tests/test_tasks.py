"""
Test Celery tasks.
"""


import os
import tempfile

import fixtures; fixtures.monkey_patch_fixture()
from fixture import SQLAlchemyFixture
from fixture.style import NamedDataStyle
from flask.ext.testing import TestCase
from nose.tools import *
from sqlalchemy import create_engine

from varda import create_app, db, models
from varda.models import Coverage, Region, User
from varda import tasks

from fixtures import CoverageData


TEST_SETTINGS = {
    'TESTING': True,
    'DATA_DIR': tempfile.mkdtemp(),
    'SECONDARY_DATA_DIR': os.path.join(os.path.dirname(__file__), 'data'),
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
        self.fixture = SQLAlchemyFixture(env=models, style=NamedDataStyle(), engine=db.engine)

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
        assert_equal(tasks.ping.apply().result, 'pong')

    def test_ping_delayed(self):
        """
        Asynchronously execute a task and get the result.

        This works, because we set CELERY_ALWAYS_EAGER to True in the test
        environment.
        """
        assert_equal(tasks.ping.delay().result, 'pong')

    def test_import_coverage(self):
        """
        Import a coverage file.
        """
        with self.fixture.data(CoverageData) as data:
            coverage = Coverage.query.get(
                data.CoverageData.unimported_exome_samtools_coverage.id)
            result = tasks.import_coverage.delay(coverage.id)
            assert_equal(result.state, 'SUCCESS')
            assert coverage.task_done
            assert_equal(Region.query.filter_by(coverage=coverage).count(), 22)

    def test_import_nonexisting_coverage(self):
        """
        Import a coverage file for nonexisting coverage resource.
        """
        with assert_raises(tasks.TaskError) as cm:
            tasks.import_coverage.delay(27)
        assert_equal(cm.exception.code, 'coverage_not_found')

    def test_import_imported_coverage(self):
        """
        Import already imported coverage.
        """
        with self.fixture.data(CoverageData) as data:
            coverage = Coverage.query.get(
                data.CoverageData.unimported_exome_samtools_coverage.id)
            result = tasks.import_coverage.delay(coverage.id)
            assert_equal(result.state, 'SUCCESS')

            with assert_raises(tasks.TaskError) as cm:
                tasks.import_coverage.delay(coverage.id)
            assert_equal(cm.exception.code, 'coverage_imported')
            assert coverage.task_done

    def test_import_coverage_duplicate(self):
        """
        Import the same coverage file twice.
        """
        with self.fixture.data(CoverageData) as data:
            coverage = Coverage.query.get(
                data.CoverageData.unimported_exome_samtools_coverage.id)
            result = tasks.import_coverage.delay(coverage.id)
            assert_equal(result.state, 'SUCCESS')

            coverage = Coverage.query.get(
                data.CoverageData.unimported_exome_samtools_coverage_2.id)
            with assert_raises(tasks.TaskError) as cm:
                tasks.import_coverage.delay(coverage.id)
            assert_equal(cm.exception.code, 'duplicate_data_source')
            assert not coverage.task_done
