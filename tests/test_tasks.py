"""
Test Celery tasks.
"""


import os
import StringIO
import tempfile

import fixtures; fixtures.monkey_patch_fixture()
from fixture import SQLAlchemyFixture
from fixture.style import NamedDataStyle
from flask.ext.testing import TestCase
from nose.tools import *
from sqlalchemy import create_engine
import vcf

from varda import create_app, db, models
from varda.models import Annotation, Coverage, DataSource, Observation, Region, User, Variation
from varda import tasks, utils

from fixtures import AnnotationData, CoverageData, DataSourceData, VariationData


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
                data.CoverageData.exome_coverage.id)
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
                data.CoverageData.exome_coverage.id)
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
                data.CoverageData.exome_coverage.id)
            result = tasks.import_coverage.delay(coverage.id)
            assert_equal(result.state, 'SUCCESS')

            coverage = Coverage.query.get(
                data.CoverageData.exome_coverage_duplicate.id)
            with assert_raises(tasks.TaskError) as cm:
                tasks.import_coverage.delay(coverage.id)
            assert_equal(cm.exception.code, 'duplicate_data_source')
            assert not coverage.task_done

    def test_import_variation(self):
        """
        Import a variation file.
        """
        with self.fixture.data(VariationData) as data:
            variation = Variation.query.get(
                data.VariationData.exome_variation.id)
            result = tasks.import_variation.delay(variation.id)
            assert_equal(result.state, 'SUCCESS')
            assert variation.task_done
            assert_equal(Observation.query.filter_by(variation=variation).count(), 16)

    def test_import_nonexisting_variation(self):
        """
        Import a variation file for nonexisting variation resource.
        """
        with assert_raises(tasks.TaskError) as cm:
            tasks.import_variation.delay(27)
        assert_equal(cm.exception.code, 'variation_not_found')

    def test_import_imported_variation(self):
        """
        Import already imported variation.
        """
        with self.fixture.data(VariationData) as data:
            variation = Variation.query.get(
                data.VariationData.exome_variation.id)
            result = tasks.import_variation.delay(variation.id)
            assert_equal(result.state, 'SUCCESS')

            with assert_raises(tasks.TaskError) as cm:
                tasks.import_variation.delay(variation.id)
            assert_equal(cm.exception.code, 'variation_imported')
            assert variation.task_done

    def test_import_variation_duplicate(self):
        """
        Import the same variation file twice.
        """
        with self.fixture.data(VariationData) as data:
            variation = Variation.query.get(
                data.VariationData.exome_variation.id)
            result = tasks.import_variation.delay(variation.id)
            assert_equal(result.state, 'SUCCESS')

            variation = Variation.query.get(
                data.VariationData.exome_variation_duplicate.id)
            with assert_raises(tasks.TaskError) as cm:
                tasks.import_variation.delay(variation.id)
            assert_equal(cm.exception.code, 'duplicate_data_source')
            assert not variation.task_done

    def test_write_annotation(self):
        """
        Annotate a variants file.

        We first import a subset of the observations with coverage.
        """
        with self.fixture.data(AnnotationData, CoverageData, VariationData) as data:
            coverage = Coverage.query.get(
                data.CoverageData.exome_subset_coverage.id)
            result = tasks.import_coverage.delay(coverage.id)
            assert coverage.task_done

            variation = Variation.query.get(
                data.VariationData.exome_subset_variation.id)
            result = tasks.import_variation.delay(variation.id)
            assert variation.task_done

            variation.sample.active = True
            db.session.commit()

            annotation = Annotation.query.get(
                data.AnnotationData.exome_annotation.id)

            result = tasks.write_annotation.delay(annotation.id)
            assert_equal(result.state, 'SUCCESS')
            assert annotation.task_done

            with annotation.annotated_data_source.data() as data:
                reader = vcf.Reader(data)
                assert_equal([(record.INFO['GLOBAL_VN'], record.INFO['GLOBAL_VF']) for record in reader],
                             [([1], [1.0]),
                              ([1], [1.0]),
                              ([1], [1.0]),
                              ([0], [0.0]),
                              ([0], [0.0]),
                              ([0], [0.0]),
                              ([1], [1.0]),
                              ([1], [1.0]),
                              ([1], [1.0]),
                              ([1], [1.0]),
                              ([1], [1.0]),
                              ([1, 1], [1.0, 0.0]),
                              ([0], [0.0]),
                              ([1], [0.0]),
                              ([1], [1.0]),
                              ([1], [1.0])])

    def test_write_nonexisting_annotation(self):
        """
        Write an annotation file for nonexisting annotation resource.
        """
        with assert_raises(tasks.TaskError) as cm:
            tasks.write_annotation.delay(27)
        assert_equal(cm.exception.code, 'annotation_not_found')

    def test_write_written_annotation(self):
        """
        Annotate an already annotated variants file.
        """
        with self.fixture.data(AnnotationData, CoverageData, VariationData) as data:
            coverage = Coverage.query.get(
                data.CoverageData.exome_subset_coverage.id)
            result = tasks.import_coverage.delay(coverage.id)
            assert coverage.task_done

            variation = Variation.query.get(
                data.VariationData.exome_subset_variation.id)
            result = tasks.import_variation.delay(variation.id)
            assert variation.task_done

            variation.sample.active = True
            db.session.commit()

            annotation = Annotation.query.get(
                data.AnnotationData.exome_annotation.id)

            result = tasks.write_annotation.delay(annotation.id)
            assert_equal(result.state, 'SUCCESS')

            with assert_raises(tasks.TaskError) as cm:
                tasks.write_annotation.delay(annotation.id)
            assert_equal(cm.exception.code, 'annotation_written')
            assert annotation.task_done

    def test_read_regions(self):
        """
        Read a file with regions.
        """
        with self.fixture.data(DataSourceData) as data:
            data_source = DataSource.query.get(
                data.DataSourceData.exome_coverage.id)
            with data_source.data() as data:
                regions = list(tasks.read_regions(data, data_source.filetype))

            assert_equal(regions,
                         [(i, 'chr20', begin, end) for i, (begin, end) in
                          enumerate([(68113, 68631),
                                     (76582, 77410),
                                     (90026, 90400),
                                     (92607, 92639),
                                     (95811, 95828),
                                     (95985, 96046),
                                     (123068, 123562),
                                     (125992, 126453),
                                     (131375, 131398),
                                     (131407, 131744),
                                     (137990, 138456),
                                     (139266, 139962),
                                     (139976, 139990),
                                     (159655, 159670),
                                     (159706, 159720),
                                     (166581, 167073),
                                     (168393, 168882),
                                     (170009, 170504),
                                     (180697, 180795),
                                     (180854, 180946),
                                     (187548, 187853),
                                     (187859, 187975)])])

    def test_read_observations(self):
        """
        Read a file with observations.
        """
        with self.fixture.data(DataSourceData) as data:
            data_source = DataSource.query.get(
                data.DataSourceData.exome_variation.id)
            with data_source.data() as data:
                observations = list(tasks.read_observations(data, data_source.filetype))

            assert_equal(observations,
                         [(i + 24, 'chr20') + observation for i, observation in
                          enumerate([(76962, 'T', 'C', 'heterozygous', 1),
                                     (126156, 'CAAA', '', 'heterozygous', 1),
                                     (126311, 'CC', '', 'heterozygous', 1),
                                     (131495, 'T', 'C', 'homozygous', 1),
                                     (131506, 'TCT', '', 'heterozygous', 1),
                                     (131657, 'A', 'G', 'homozygous', 1),
                                     (138004, 'G', 'C', 'homozygous', 1),
                                     (138179, 'C', '', 'heterozygous', 1),
                                     (139362, 'G', 'A', 'homozygous', 1),
                                     (139745, 'T', 'C', 'homozygous', 1),
                                     (139841, 'A', 'T', 'homozygous', 1),
                                     (139916, '', 'AA', 'homozygous', 1),
                                     (166727, 'G', 'A', 'heterozygous', 1),
                                     (168466, 'T', 'A', 'heterozygous', 1),
                                     (168728, 'T', 'A', 'homozygous', 1),
                                     (168781, 'G', 'T', 'heterozygous', 1)])])

    def test_read_observations_likelihoods(self):
        """
        Read a file with observations and prefer genotype likelihoods.
        """
        with self.fixture.data(DataSourceData) as data:
            data_source = DataSource.query.get(
                data.DataSourceData.exome_variation.id)
            with data_source.data() as data:
                observations = list(tasks.read_observations(data, data_source.filetype,
                                                            prefer_genotype_likelihoods=True))

            assert_equal(observations,
                         [(24, 'chr20', 76962, 'T', 'C', 'heterozygous', 1),
                          (25, 'chr20', 126156, 'CAAA', '', 'heterozygous', 1),
                          (26, 'chr20', 126311, 'CC', '', 'homozygous', 1),
                          (27, 'chr20', 131495, 'T', 'C', 'homozygous', 1),
                          (28, 'chr20', 131506, 'TCT', '', 'heterozygous', 1),
                          (29, 'chr20', 131657, 'A', 'G', 'homozygous', 1),
                          (30, 'chr20', 138004, 'G', 'C', 'homozygous', 1),
                          (32, 'chr20', 139362, 'G', 'A', 'homozygous', 1),
                          (33, 'chr20', 139745, 'T', 'C', 'homozygous', 1),
                          (34, 'chr20', 139841, 'A', 'T', 'homozygous', 1),
                          (35, 'chr20', 139916, '', 'AA', 'homozygous', 1),
                          (36, 'chr20', 166727, 'G', 'A', 'heterozygous', 1),
                          (37, 'chr20', 168466, 'T', 'A', 'heterozygous', 1),
                          (38, 'chr20', 168728, 'T', 'A', 'homozygous', 1),
                          (39, 'chr20', 168781, 'G', 'T', 'heterozygous', 1)])

    def test_read_observations_no_genotypes(self):
        """
        Read a file with observations, ignoring genotypes.
        """
        with self.fixture.data(DataSourceData) as data:
            data_source = DataSource.query.get(
                data.DataSourceData.exome_variation.id)
            with data_source.data() as data:
                observations = list(tasks.read_observations(data, data_source.filetype,
                                                            use_genotypes=False))

            assert_equal(observations,
                         [(i + 24 if i < 11 else i + 25, 'chr20') + observation for i, observation in
                          enumerate([(76962, 'T', 'C', None, 1),
                                     (126156, 'CAAA', '', None, 1),
                                     (126311, 'CC', '', None, 1),
                                     (131495, 'T', 'C', None, 1),
                                     (131506, 'TCT', '', None, 1),
                                     (131657, 'A', 'G', None, 1),
                                     (138004, 'G', 'C', None, 1),
                                     (138179, 'C', '', None, 1),
                                     (139362, 'G', 'A', None, 1),
                                     (139745, 'T', 'C', None, 1),
                                     (139841, 'A', 'T', None, 1),
                                     (166727, 'G', 'A', None, 1),
                                     (168466, 'T', 'A', None, 1),
                                     (168728, 'T', 'A', None, 1),
                                     (168781, 'G', 'T', None, 1)])])

    def test_read_observations_gtc(self):
        """
        Read a file with observations, using GTC field.
        """
        with self.fixture.data(DataSourceData) as data:
            data_source = DataSource.query.get(
                data.DataSourceData.gonl_summary_variation.id)
            with data_source.data() as data:
                observations = list(tasks.read_observations(data, data_source.filetype))

            assert_equal([o[2:] for o in observations[:15]],
                         [(60309, 'G', 'T', 'heterozygous', 4),
                          (60573, 'T', 'C', 'heterozygous', 1),
                          (60828, 'T', 'G', 'heterozygous', 6),
                          (61098, 'C', 'T', 'heterozygous', 163),
                          (61098, 'C', 'T', 'homozygous', 31),
                          (61270, 'A', 'C', 'heterozygous', 20),
                          (61682, 'C', 'T', 'heterozygous', 1),
                          (61795, 'G', 'T', 'heterozygous', 203),
                          (61795, 'G', 'T', 'homozygous', 64),
                          (61803, 'A', 'G', 'heterozygous', 1),
                          (61955, 'C', 'T', 'heterozygous', 1),
                          (62255, 'T', 'C', 'heterozygous', 4),
                          (62731, 'C', 'A', 'heterozygous', 93),
                          (62731, 'C', 'A', 'homozygous', 6),
                          (63008, 'C', 'A', 'heterozygous', 1)])

    def test_read_observations_with_filtered(self):
        """
        Read a file with observations and include filtered.
        """
        with self.fixture.data(DataSourceData) as data:
            data_source = DataSource.query.get(
                data.DataSourceData.exome_variation_filtered.id)
            with data_source.data() as data:
                observations = list(tasks.read_observations(data, data_source.filetype,
                                                            skip_filtered=False))

            assert_equal(observations,
                         [(i + 26, 'chr20') + observation for i, observation in
                          enumerate([(76962, 'T', 'C', 'heterozygous', 1),
                                     (126156, 'CAAA', '', 'heterozygous', 1),
                                     (126311, 'CC', '', 'heterozygous', 1),
                                     (131495, 'T', 'C', 'homozygous', 1),
                                     (131506, 'TCT', '', 'heterozygous', 1),
                                     (131657, 'A', 'G', 'homozygous', 1),
                                     (138004, 'G', 'C', 'homozygous', 1),
                                     (138179, 'C', '', 'heterozygous', 1),
                                     (139362, 'G', 'A', 'homozygous', 1),
                                     (139745, 'T', 'C', 'homozygous', 1),
                                     (139841, 'A', 'T', 'homozygous', 1),
                                     (139916, '', 'AA', 'homozygous', 1),
                                     (166727, 'G', 'A', 'heterozygous', 1),
                                     (168466, 'T', 'A', 'heterozygous', 1),
                                     (168728, 'T', 'A', 'homozygous', 1),
                                     (168781, 'G', 'T', 'heterozygous', 1)])])

    def test_read_observations_without_filtered(self):
        """
        Read a file with observations and discard filtered.
        """
        with self.fixture.data(DataSourceData) as data:
            data_source = DataSource.query.get(
                data.DataSourceData.exome_variation_filtered.id)
            with data_source.data() as data:
                observations = list(tasks.read_observations(data, data_source.filetype,
                                                            skip_filtered=True))

            assert_equal(observations,
                         [(26, 'chr20', 76962, 'T', 'C', 'heterozygous', 1),
                          (27, 'chr20', 126156, 'CAAA', '', 'heterozygous', 1),
                          (28, 'chr20', 126311, 'CC', '', 'heterozygous', 1),
                          (30, 'chr20', 131506, 'TCT', '', 'heterozygous', 1),
                          (31, 'chr20', 131657, 'A', 'G', 'homozygous', 1),
                          (32, 'chr20', 138004, 'G', 'C', 'homozygous', 1),
                          (33, 'chr20', 138179, 'C', '', 'heterozygous', 1),
                          (34, 'chr20', 139362, 'G', 'A', 'homozygous', 1),
                          (36, 'chr20', 139841, 'A', 'T', 'homozygous', 1),
                          (37, 'chr20', 139916, '', 'AA', 'homozygous', 1),
                          (38, 'chr20', 166727, 'G', 'A', 'heterozygous', 1),
                          (39, 'chr20', 168466, 'T', 'A', 'heterozygous', 1),
                          (40, 'chr20', 168728, 'T', 'A', 'homozygous', 1),
                          (41, 'chr20', 168781, 'G', 'T', 'heterozygous', 1)])

    def test_annotate_variants(self):
        """
        Annotate a file with observation frequencies.

        We first import a subset of the observations with coverage.
        """
        with self.fixture.data(CoverageData, DataSourceData, VariationData) as data:
            coverage = Coverage.query.get(
                data.CoverageData.exome_subset_coverage.id)
            result = tasks.import_coverage.delay(coverage.id)
            assert coverage.task_done

            variation = Variation.query.get(
                data.VariationData.exome_subset_variation.id)
            result = tasks.import_variation.delay(variation.id)
            assert variation.task_done

            variation.sample.active = True
            db.session.commit()

            data_source = DataSource.query.get(
                data.DataSourceData.exome_variation.id)
            annotated_file = StringIO.StringIO()

            with data_source.data() as data:
                checksum, records = utils.digest(data)

            with data_source.data() as data:
                tasks.annotate_variants(data, annotated_file,
                                        original_filetype=data_source.filetype,
                                        annotated_filetype='vcf',
                                        original_records=records,
                                        exclude_checksum=checksum)

            lines = annotated_file.getvalue().split('\n')
            reader = vcf.Reader(lines)

            assert_equal([(record.INFO['GLOBAL_VN'], record.INFO['GLOBAL_VF']) for record in reader],
                         [([1], [1.0]),
                          ([1], [1.0]),
                          ([1], [1.0]),
                          ([0], [0.0]),
                          ([0], [0.0]),
                          ([0], [0.0]),
                          ([1], [1.0]),
                          ([1], [1.0]),
                          ([1], [1.0]),
                          ([1], [1.0]),
                          ([1], [1.0]),
                          ([1, 1], [1.0, 0.0]),
                          ([0], [0.0]),
                          ([1], [0.0]),
                          ([1], [1.0]),
                          ([1], [1.0])])
