"""
High-level REST API unit tests.

Todo: Look at http://packages.python.org/Flask-Testing/
"""


from StringIO import StringIO
import json
import tempfile
import time

from nose.tools import *
import vcf

from varda import create_app, db
from varda.models import User


TEST_SETTINGS = {
    'TESTING': True,
    'FILES_DIR': tempfile.mkdtemp(),
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


def auth_header(login='admin', password='test'):
    """
    HTTP Basic Authentication header for a test user.
    """
    user = '%s:%s' % (login, password)
    return ('AUTHORIZATION', 'BASIC ' + user.encode('base64'))


class TestApi():
    """
    High-level unit tests, using the REST API entry points of Varda.

    Todo: Split into several test classes.
    """
    def setup(self):
        """
        Run once before every test. Setup the test database.
        """
        self.app = create_app(TEST_SETTINGS)
        self.client = self.app.test_client()
        with self.app.test_request_context():
            db.create_all()
            admin = User('Test Admin', 'admin', 'test', roles=['admin'])
            db.session.add(admin)
            trader = User('Test Trader', 'trader', 'test', roles=['importer', 'trader'])
            db.session.add(trader)
            user = User('Test User', 'user', 'test', roles=[])
            db.session.add(user)
            db.session.commit()

    def teardown(self):
        """
        Run once after every test. Drop the test database.
        """
        with self.app.test_request_context():
            db.session.remove()
            db.drop_all()

    @property
    def uri_root(self):
        return (self.app.config['API_URL_PREFIX'] or '') + '/'

    @property
    def uri_users(self):
        r = self.client.get(self.uri_root)
        return json.loads(r.data)['api']['collections']['users']

    @property
    def uri_samples(self):
        r = self.client.get(self.uri_root)
        return json.loads(r.data)['api']['collections']['samples']

    @property
    def uri_data_sources(self):
        r = self.client.get(self.uri_root)
        return json.loads(r.data)['api']['collections']['data_sources']

    def test_root(self):
        """
        Dummy test.
        """
        r = self.client.get(self.uri_root)
        assert_equal(r.status_code, 200)
        assert_equal(json.loads(r.data)['api']['status'], 'ok')

    def test_parameter_type(self):
        """
        Test request with incorrect parameter type.
        """
        r = self.client.post(self.uri_samples + 'abc', headers=[auth_header()])
        assert_equal(r.status_code, 404)

    def test_authentication(self):
        """
        Test authentication stuff.
        """
        r = self.client.get(self.uri_users)
        assert_equal(r.status_code, 401)

        r = self.client.get(self.uri_users, headers=[auth_header(password='incorrect')])
        assert_equal(r.status_code, 401)

        r = self.client.get(self.uri_users, headers=[auth_header()])
        assert_equal(r.status_code, 200)

        r = self.client.get(self.uri_users, headers=[auth_header(login='user', password='test')])
        assert_equal(r.status_code, 403)

        r = self.client.get(self.uri_root)
        assert_equal(r.status_code, 200)

        r = self.client.get(self.uri_root, headers=[auth_header(login='user', password='test')])
        assert_equal(r.status_code, 200)

    def test_user_formdata(self):
        """
        Test user creation with HTTP formdata payload.
        """
        data = {'name': 'Test Tester',
                'login': 'test',
                'password': 'test'}
        r = self.client.post(self.uri_users, data=data, headers=[auth_header()])
        assert_equal(r.status_code, 201)
        # Todo: Something better than the replace.
        user = r.headers['Location'].replace('http://localhost', '')

        r = self.client.get(user, headers=[auth_header()])
        assert_equal(r.status_code, 200)

    def test_user_json(self):
        """
        Test user creation with a json payload.
        """
        data = {'name': 'Test Tester',
                'login': 'test',
                'password': 'test',
                'roles': []}
        r = self.client.post(self.uri_users, data=json.dumps(data), content_type='application/json', headers=[auth_header()])
        assert_equal(r.status_code, 201)
        # Todo: Something better than the replace.
        user = r.headers['Location'].replace('http://localhost', '')

        r = self.client.get(user, headers=[auth_header()])
        assert_equal(r.status_code, 200)

    def test_1kg(self):
        """
        Import 1KG samples without coverage track.
        """
        self._import('1000 Genomes', 'tests/data/1kg.vcf', pool_size=1092)

    def test_gonl(self):
        """
        Import GoNL samples without coverage track.
        """
        self._import('Genome of the Netherlands', 'tests/data/gonl.vcf', pool_size=767)

    def test_exome(self):
        """
        Import and annotate exome sample with coverage track.

        All annotations should have observation and coverage 1.
        """
        sample, vcf_data_source, _ = self._import('Test sample', 'tests/data/exome-samtools.vcf', 'tests/data/exome-samtools.bed')
        annotated_data_source = self._annotate(vcf_data_source, exclude=[sample], include=[('SAMPLE', sample)])

        # Download annotation and see if we can parse it as VCF
        r = self.client.get(annotated_data_source, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        annotated_data_source_data = json.loads(r.data)['data_source']['data']
        r = self.client.get(annotated_data_source_data, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        assert_equal(r.content_type, 'application/x-gzip')
        open('/tmp/test_exome.vcf.gz', 'w').write(r.data)
        for _ in vcf.Reader(StringIO(r.data), compressed=True):
            pass

    def test_exome_subset(self):
        """
        Import exome sample with coverage track and import and annotate a
        subset of it.

        All annotations should have observation and coverage 2.
        """
        self._import('Test sample', 'tests/data/exome-samtools.vcf', 'tests/data/exome-samtools.bed')
        sample, vcf_data_source, _ = self._import('Test subset', 'tests/data/exome-samtools-subset.vcf', 'tests/data/exome-samtools-subset.bed')
        annotated_data_source = self._annotate(vcf_data_source, exclude=[sample])

        # Download annotation and see if we can parse it as VCF
        r = self.client.get(annotated_data_source, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        annotated_data_source_data = json.loads(r.data)['data_source']['data']
        r = self.client.get(annotated_data_source_data, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        assert_equal(r.content_type, 'application/x-gzip')
        open('/tmp/test_exome_subset.vcf.gz', 'w').write(r.data)
        for _ in vcf.Reader(StringIO(r.data), compressed=True):
            pass

    def test_exome_superset(self):
        """
        Import exome sample with coverage track and import and annotate a
        superset of it.

        All annotations should have observation and coverage (2, 2), (1, 2), or (1, 1).
        """
        sample, vcf_data_source, _ = self._import('Test sample', 'tests/data/exome-samtools.vcf', 'tests/data/exome-samtools.bed')
        self._import('Test subset', 'tests/data/exome-samtools-subset.vcf', 'tests/data/exome-samtools-subset.bed')
        annotated_data_source = self._annotate(vcf_data_source, exclude=[sample])

        # Download annotation and see if we can parse it as VCF
        r = self.client.get(annotated_data_source, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        annotated_data_source_data = json.loads(r.data)['data_source']['data']
        r = self.client.get(annotated_data_source_data, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        assert_equal(r.content_type, 'application/x-gzip')
        open('/tmp/test_exome_superset.vcf.gz', 'w').write(r.data)
        for _ in vcf.Reader(StringIO(r.data), compressed=True):
            pass

    def test_duplicate_import(self):
        """
        Importing the same file twice should not be possible.
        """
        # Todo: Better test.
        self._import('Test sample 1', 'tests/data/exome-samtools.vcf', 'tests/data/exome-samtools.bed')
        try:
            self._import('Test sample 2', 'tests/data/exome-samtools.vcf', 'tests/data/exome-samtools.bed')
        except AssertionError:
            pass
        else:
            assert False

    def test_trader(self):
        """
        A trader can only annotate after importing and activating.
        """
        # Create sample
        data = {'name': 'Test sample',
                'pool_size': 1}
        r = self.client.post(self.uri_samples, data=json.dumps(data), content_type='application/json', headers=[auth_header(login='trader', password='test')])
        assert_equal(r.status_code, 201)
        sample = json.loads(r.data)['sample']

        # Upload VCF
        data = {'name': 'Test observations',
                'filetype': 'vcf',
                'data': open('tests/data/exome-samtools.vcf')}
        r = self.client.post(self.uri_data_sources, data=data, headers=[auth_header(login='trader', password='test')])
        assert_equal(r.status_code, 201)
        # Todo: Something better than the replace.
        vcf_data_source = r.headers['Location'].replace('http://localhost', '')

        # Get annotations URI for the observations data source
        r = self.client.get(vcf_data_source, headers=[auth_header(login='trader', password='test')])
        assert_equal(r.status_code, 200)
        annotations = json.loads(r.data)['data_source']['annotations']

        # Annotate observations
        data = {'exclude_samples': [sample]}
        r = self.client.post(annotations, data=json.dumps(data), content_type='application/json', headers=[auth_header(login='trader', password='test')])
        assert_equal(r.status_code, 400)

        # Get variations URI for this sample
        r = self.client.get(sample, headers=[auth_header(login='trader', password='test')])
        assert_equal(r.status_code, 200)
        variations = json.loads(r.data)['sample']['variations']

        # Import observations
        data = {'data_source': vcf_data_source}
        r = self.client.post(variations, data=data, headers=[auth_header(login='trader', password='test')])
        assert_equal(r.status_code, 202)
        variation_import_status = json.loads(r.data)['variation_import_status']

        # Wait for importing
        # Note: Bogus since during testing tasks return synchronously
        for _ in range(5):
            r = self.client.get(variation_import_status, headers=[auth_header(login='trader', password='test')])
            assert_equal(r.status_code, 200)
            status = json.loads(r.data)['status']
            if status['ready']:
                break
            time.sleep(1)
        else:
            assert False

        # Annotate observations
        data = {'exclude_samples': [sample]}
        r = self.client.post(annotations, data=json.dumps(data), content_type='application/json', headers=[auth_header(login='trader', password='test')])
        assert_equal(r.status_code, 400)

        # Activate sample
        data = {'active': True}
        r = self.client.patch(sample, data=json.dumps(data), content_type='application/json', headers=[auth_header(login='trader', password='test')])
        assert_equal(r.status_code, 200)

        # Annotate observations
        data = {'exclude_samples': [sample]}
        r = self.client.post(annotations, data=json.dumps(data), content_type='application/json', headers=[auth_header(login='trader', password='test')])
        assert_equal(r.status_code, 202)

    def _annotate(self, vcf_data_source, exclude=None, include=None):
        """
        Annotate observations and return the annotated data source URI.
        """
        exclude = exclude or []
        include = include or []

        # Get annotations URI for the observations data source
        r = self.client.get(vcf_data_source, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        annotations = json.loads(r.data)['data_source']['annotations']

        # Annotate observations
        data = {'exclude_samples': exclude,
                'include_samples': include}
        r = self.client.post(annotations, data=json.dumps(data), content_type='application/json', headers=[auth_header()])
        assert_equal(r.status_code, 202)
        annotation_write_status = json.loads(r.data)['annotation_write_status']

        # Wait for writing
        # Note: Bogus since during testing tasks return synchronously
        annotation = None
        for _ in range(5):
            r = self.client.get(annotation_write_status, headers=[auth_header()])
            assert_equal(r.status_code, 200)
            status = json.loads(r.data)['status']
            if status['ready']:
                annotation = status['annotation']
                break
            time.sleep(1)
        else:
            assert False

        # Get annotated data source URI
        r = self.client.get(annotation, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        return json.loads(r.data)['annotation']['annotated_data_source']

    def _import(self, name, vcf_file, bed_file=None, pool_size=1):
        """
        Import observations and coverage. Return a tuple with URIs for the
        sample, VCF data source, and BED data source.
        """
        # Create sample
        data = {'name': name,
                'coverage_profile': bed_file is not None,
                'pool_size': pool_size}
        r = self.client.post(self.uri_samples, data=json.dumps(data), content_type='application/json', headers=[auth_header()])
        assert_equal(r.status_code, 201)
        sample = json.loads(r.data)['sample']

        # Upload VCF
        data = {'name': '%s observations' % name,
                'filetype': 'vcf',
                'data': open(vcf_file)}
        r = self.client.post(self.uri_data_sources, data=data, headers=[auth_header()])
        assert_equal(r.status_code, 201)
        # Todo: Something better than the replace.
        vcf_data_source = r.headers['Location'].replace('http://localhost', '')

        # Upload BED
        if bed_file:
            data = {'name': '%s coverage' % name,
                    'filetype': 'bed',
                    'data': open(bed_file)}
            r = self.client.post(self.uri_data_sources, data=data, headers=[auth_header()])
            assert_equal(r.status_code, 201)
            # Todo: Something better than the replace.
            bed_data_source = r.headers['Location'].replace('http://localhost', '')
        else:
            bed_data_source = None

        # Get variation and coverage URIs for this sample
        r = self.client.get(sample, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        variations = json.loads(r.data)['sample']['variations']
        coverages = json.loads(r.data)['sample']['coverages']

        # Import observations
        data = {'data_source': vcf_data_source}
        r = self.client.post(variations, data=data, headers=[auth_header()])
        assert_equal(r.status_code, 202)
        variation_import_status = json.loads(r.data)['variation_import_status']

        # Wait for importing
        # Note: Bogus since during testing tasks return synchronously
        variation = None
        for _ in range(5):
            r = self.client.get(variation_import_status, headers=[auth_header()])
            assert_equal(r.status_code, 200)
            status = json.loads(r.data)['status']
            if status['ready']:
                variation = status['variation']
                break
            time.sleep(1)
        else:
            assert False

        # Import regions
        if bed_data_source:
            data = {'data_source': bed_data_source}
            r = self.client.post(coverages, data=data, headers=[auth_header()])
            assert_equal(r.status_code, 202)
            coverage_import_status = json.loads(r.data)['coverage_import_status']

            # Wait for importing
            # Note: Bogus since during testing tasks return synchronously
            coverate = None
            for _ in range(5):
                r = self.client.get(coverage_import_status, headers=[auth_header()])
                assert_equal(r.status_code, 200)
                status = json.loads(r.data)['status']
                if status['ready']:
                    coverage = status['coverage']
                    break
                time.sleep(1)
            else:
                assert False

        # Activate sample
        data = {'active': True}
        r = self.client.patch(sample, data=json.dumps(data), content_type='application/json', headers=[auth_header()])
        assert_equal(r.status_code, 200)

        return sample, vcf_data_source, bed_data_source

    def test_import_1kg(self):
        """
        Import 1000 genomes variants.
        """
        return  # disabled due to population-study refactoring
        # Create sample
        data = {'name': '1KG',
                'coverage_profile': False,
                'pool_size': 1092}
        r = self.client.post(self.uri_samples, data=json.dumps(data), content_type='application/json', headers=[auth_header()])
        assert_equal(r.status_code, 201)
        sample = json.loads(r.data)['sample']

        # Get observations URI for this sample
        r = self.client.get(sample, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        observations = json.loads(r.data)['sample']['observations']

        # Upload VCF
        data = {'name': 'Some variants',
                'filetype': 'vcf',
                'data': open('tests/data/1kg.vcf')}
        r = self.client.post(self.uri_data_sources, data=data, headers=[auth_header()])
        assert_equal(r.status_code, 201)
        # Todo: Something better than the replace.
        data_source = r.headers['Location'].replace('http://localhost', '')

        # Import VCF
        data = {'data_source': data_source}
        r = self.client.post(observations, data=data, headers=[auth_header()])
        assert_equal(r.status_code, 202)
        wait = json.loads(r.data)['wait']

        # Check success
        r = self.client.get(wait, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        ok_(json.loads(r.data)['observations']['ready'])
