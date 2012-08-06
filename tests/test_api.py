"""
High-level REST API unit tests.

Todo: Look at http://packages.python.org/Flask-Testing/
Todo: Suppress the annoying log messages.
"""


import tempfile
import json

from nose.tools import *

from varda import create_app, db
from varda.models import User


TEST_SETTINGS = {
    'TESTING': True,
    'FILES_DIR': tempfile.mkdtemp(),
    'SQLALCHEMY_DATABASE_URI': 'sqlite://',
    'BROKER_TRANSPORT': 'memory',
    'CELERY_ALWAYS_EAGER': True,
    'CELERY_EAGER_PROPAGATES_EXCEPTIONS': True
}


def auth_header(login='test', password='test'):
    """
    HTTP Basic Authentication header for a test user.
    """
    return ('AUTHORIZATION', 'BASIC ' + 'test:test'.encode('base64'))


class TestApi():
    """
    High-level unit tests, using the REST API entry points of Varda.
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

    def test_root(self):
        """
        Dummy test.
        """
        r = self.client.get('/')
        assert 'contact' in r.data

    def test_exome(self):
        """
        Import and annotate exome sample with coverage track.
        """
        # Create sample
        data = {'name': 'Exome sample',
                'coverage_threshold': 8,
                'pool_size': 1}
        r = self.client.post('/samples', data=data, headers=[auth_header()])
        assert_equal(r.status_code, 201)
        sample = json.loads(r.data)['sample']

        # Upload VCF
        data = {'name': 'Some exome observations',
                'filetype': 'vcf',
                'data': open('tests/data/exome-samtools.vcf')}
        r = self.client.post('/data_sources', data=data, headers=[auth_header()])
        assert_equal(r.status_code, 201)
        # Todo: Something better than the replace.
        vcf_data_source = r.headers['Location'].replace('http://localhost', '')

        # Upload BED
        data = {'name': 'Some exome coverage',
                'filetype': 'bed',
                'data': open('tests/data/exome-samtools.bed')}
        r = self.client.post('/data_sources', data=data, headers=[auth_header()])
        assert_equal(r.status_code, 201)
        # Todo: Something better than the replace.
        bed_data_source = r.headers['Location'].replace('http://localhost', '')

        # Get observations and regions URIs for this sample
        r = self.client.get(sample, headers=[auth_header()])
        observations = json.loads(r.data)['sample']['observations']
        regions = json.loads(r.data)['sample']['regions']

        # Import observations
        data = {'data_source': vcf_data_source}
        r = self.client.post(observations, data=data, headers=[auth_header()])
        assert_equal(r.status_code, 202)
        observations_wait = json.loads(r.data)['wait']

        # Fake check (all results are direct in the unit test setting)
        r = self.client.get(observations_wait, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        ok_(json.loads(r.data)['observations']['ready'])

        # Import regions
        data = {'data_source': bed_data_source}
        r = self.client.post(regions, data=data, headers=[auth_header()])
        assert_equal(r.status_code, 202)
        regions_wait = json.loads(r.data)['wait']

        # Fake check (all results are direct in the unit test setting)
        r = self.client.get(regions_wait, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        ok_(json.loads(r.data)['regions']['ready'])

        # Get annotations URI for the observations data source
        r = self.client.get(vcf_data_source, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        annotations = json.loads(r.data)['data_source']['annotations']

        # Annotate observations
        r = self.client.post(annotations, headers=[auth_header()])
        assert_equal(r.status_code, 202)
        annotation_wait = json.loads(r.data)['wait']
        # Note: This API diverges only for the unit test setting
        annotation = json.loads(r.data)['annotation']['uri']

        # Fake check (all results are direct in the unit test setting)
        r = self.client.get(annotation_wait, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        ok_(json.loads(r.data)['annotation']['ready'])

        # Download annotation
        r = self.client.get(annotation, headers=[auth_header()])
        open('/tmp/jaja', 'w').write(r.data)

    def test_import_1kg(self):
        """
        Import 1000 genomes variants.
        """
        return  # disabled due to population-study refactoring
        # Create sample
        data = {'name': '1KG',
                'coverage_threshold': 6,
                'pool_size': 1092}
        r = self.client.post('/samples', data=data, headers=[auth_header()])
        assert_equal(r.status_code, 201)
        sample = json.loads(r.data)['sample']

        # Get observations URI for this sample
        r = self.client.get(sample, headers=[auth_header()])
        observations = json.loads(r.data)['sample']['observations']

        # Upload VCF
        data = {'name': 'Some variants',
                'filetype': 'vcf',
                'data': open('tests/data/1kg.vcf')}
        r = self.client.post('/data_sources', data=data, headers=[auth_header()])
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
