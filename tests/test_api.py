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
from varda.models import Group, Sample, User


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
    def uri_genome(self):
        r = self.client.get(self.uri_root)
        return json.loads(r.data)['root']['genome']['uri']

    @property
    def uri_authentication(self):
        r = self.client.get(self.uri_root)
        return json.loads(r.data)['root']['authentication']['uri']

    @property
    def uri_users(self):
        r = self.client.get(self.uri_root)
        return json.loads(r.data)['root']['user_collection']['uri']

    @property
    def uri_groups(self):
        r = self.client.get(self.uri_root)
        return json.loads(r.data)['root']['group_collection']['uri']

    @property
    def uri_tokens(self):
        r = self.client.get(self.uri_root)
        return json.loads(r.data)['root']['token_collection']['uri']

    @property
    def uri_samples(self):
        r = self.client.get(self.uri_root)
        return json.loads(r.data)['root']['sample_collection']['uri']

    @property
    def uri_variations(self):
        r = self.client.get(self.uri_root)
        return json.loads(r.data)['root']['variation_collection']['uri']

    @property
    def uri_coverages(self):
        r = self.client.get(self.uri_root)
        return json.loads(r.data)['root']['coverage_collection']['uri']

    @property
    def uri_data_sources(self):
        r = self.client.get(self.uri_root)
        return json.loads(r.data)['root']['data_source_collection']['uri']

    @property
    def uri_annotations(self):
        r = self.client.get(self.uri_root)
        return json.loads(r.data)['root']['annotation_collection']['uri']

    @property
    def uri_variants(self):
        r = self.client.get(self.uri_root)
        return json.loads(r.data)['root']['variant_collection']['uri']

    def test_root(self):
        """
        Dummy test.
        """
        r = self.client.get(self.uri_root)
        assert_equal(r.status_code, 200)
        assert_equal(json.loads(r.data)['root']['status'], 'ok')

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
        r = self.client.get(self.uri_users, headers=[('Range', 'items=0-20')])
        assert_equal(r.status_code, 401)

        r = self.client.get(self.uri_users, headers=[auth_header(password='incorrect'), ('Range', 'items=0-20')])
        assert_equal(r.status_code, 401)

        r = self.client.get(self.uri_users, headers=[auth_header(), ('Range', 'items=0-20')])
        assert_equal(r.status_code, 206)

        r = self.client.get(self.uri_users, headers=[auth_header(login='user', password='test'), ('Range', 'items=0-20')])
        assert_equal(r.status_code, 403)

        r = self.client.get(self.uri_root)
        assert_equal(r.status_code, 200)

        r = self.client.get(self.uri_root, headers=[auth_header(login='user', password='test')])
        assert_equal(r.status_code, 200)

    def test_token_authentication(self):
        """
        Test authentication by token.
        """
        r = self.client.get(self.uri_users, headers=[('Range', 'items=0-20')])
        assert_equal(r.status_code, 401)

        r = self.client.get(self.uri_authentication)
        assert_equal(r.status_code, 200)
        assert_equal(None, json.loads(r.data)['authentication']['user'])

        r = self.client.get(self.uri_authentication, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        user = json.loads(r.data)['authentication']['user']['uri']

        data = {'name': 'test token',
                'user': user}
        r = self.client.post(self.uri_tokens, data=data, headers=[auth_header()])
        assert_equal(r.status_code, 201)
        key = json.loads(r.data)['token']['key']

        token_header = ('AUTHORIZATION', 'Token ' + key)

        r = self.client.get(self.uri_authentication, headers=[token_header])
        assert_equal(r.status_code, 200)
        assert_equal(user, json.loads(r.data)['authentication']['user']['uri'])

        r = self.client.get(self.uri_users, headers=[token_header, ('Range', 'items=0-20')])
        assert_equal(r.status_code, 206)

        data = {'name': 'test token',
                'user': user}
        r = self.client.post(self.uri_tokens, data=data, headers=[token_header])
        assert_equal(r.status_code, 401)
        assert_equal('basic_auth_required', json.loads(r.data)['error']['code'])

        token_header = ('AUTHORIZATION', 'Token boguskey')

        r = self.client.get(self.uri_users, headers=[token_header, ('Range', 'items=0-20')])
        assert_equal(r.status_code, 401)


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
        sample, vcf_data_source, _ = self._import('Test sample', 'tests/data/exome.vcf', 'tests/data/exome.bed')
        annotated_data_source = self._annotate(vcf_data_source, queries=['sample:%s' % sample])

        # Download annotation and see if we can parse it as VCF
        r = self.client.get(annotated_data_source, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        annotated_data_source_data = json.loads(r.data)['data_source']['data']['uri']
        r = self.client.get(annotated_data_source_data, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        assert_equal(r.content_type, 'application/x-gzip')

        reader = vcf.Reader(StringIO(r.data), compressed=True)
        assert_equal([(record.INFO['Q1_VN'], record.INFO['Q1_VF']) for record in reader],
                     [([1], [1.0]),
                      ([1], [1.0]),
                      ([1], [1.0]),
                      ([1], [1.0]),
                      ([1], [1.0]),
                      ([1], [1.0]),
                      ([1], [1.0]),
                      ([1], [1.0]),
                      ([1], [1.0]),
                      ([1], [1.0]),
                      ([1], [1.0]),
                      ([1, 1], [1.0, 0.0]),
                      ([1], [1.0]),
                      ([1], [1.0]),
                      ([1], [1.0]),
                      ([1], [1.0])])

    def test_variant(self):
        """
        Import and annotate exome sample with coverage track, check variant
        frequency.
        """
        self._import('Test sample', 'tests/data/exome.vcf', 'tests/data/exome.bed')

        data = {'chromosome': 'chr20',
                'position': 139745,
                'reference': 'T',
                'observed': 'C'}
        r = self.client.post(self.uri_variants, data=data, headers=[auth_header(login='admin', password='test')])
        assert_equal(r.status_code, 201)
        variant = json.loads(r.data)['variant']['uri']

        data = {'queries': [{'name': 'GLOBAL', 'expression': '*'}]}
        r = self.client.get(variant, data=json.dumps(data),
                            content_type='application/json',
                            headers=[auth_header(login='admin', password='test')])
        assert_equal(r.status_code, 200)
        assert_equal(1.0, json.loads(r.data)['variant']['annotations']['GLOBAL']['frequency'])

    def test_exome_subset(self):
        """
        Import exome sample with coverage track and import and annotate a
        subset of it.

        All annotations should have observation and coverage 1.
        """
        self._import('Test sample', 'tests/data/exome.vcf', 'tests/data/exome.bed')
        sample, vcf_data_source, _ = self._import('Test subset', 'tests/data/exome-subset.vcf', 'tests/data/exome-subset.bed')
        annotated_data_source = self._annotate(vcf_data_source, queries=['*'])

        # Download annotation and see if we can parse it as VCF
        r = self.client.get(annotated_data_source, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        annotated_data_source_data = json.loads(r.data)['data_source']['data']['uri']
        r = self.client.get(annotated_data_source_data, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        assert_equal(r.content_type, 'application/x-gzip')

        reader = vcf.Reader(StringIO(r.data), compressed=True)
        assert_equal([(record.INFO['Q1_VN'], record.INFO['Q1_VF']) for record in reader],
                     [([1], [1.0]),
                      ([1], [1.0]),
                      ([1], [1.0]),
                      ([1], [1.0]),
                      ([1], [1.0]),
                      ([1], [1.0]),
                      ([1], [1.0]),
                      ([1], [1.0]),
                      ([1, 1], [1.0, 0.0]),
                      ([1], [1.0]),
                      ([1], [1.0])])

    def test_exome_superset(self):
        """
        Import exome sample with coverage track and import and annotate a
        superset of it.

        All annotations should have observation and coverage (0, 0) or (1, 0)
        or (1, 1).
        """
        sample, vcf_data_source, _ = self._import('Test sample', 'tests/data/exome.vcf', 'tests/data/exome.bed')
        self._import('Test subset', 'tests/data/exome-subset.vcf', 'tests/data/exome-subset.bed')
        annotated_data_source = self._annotate(vcf_data_source, queries=['*'])

        # Download annotation and see if we can parse it as VCF
        r = self.client.get(annotated_data_source, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        annotated_data_source_data = json.loads(r.data)['data_source']['data']['uri']
        r = self.client.get(annotated_data_source_data, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        assert_equal(r.content_type, 'application/x-gzip')

        reader = vcf.Reader(StringIO(r.data), compressed=True)
        assert_equal([(record.INFO['Q1_VN'], record.INFO['Q1_VF']) for record in reader],
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

    def test_duplicate_import(self):
        """
        Importing the same file twice should not be possible.
        """
        # Todo: Better test.
        self._import('Test sample 1', 'tests/data/exome.vcf', 'tests/data/exome.bed')
        try:
            self._import('Test sample 2', 'tests/data/exome.vcf', 'tests/data/exome.bed')
        except AssertionError:
            pass
        else:
            assert False

    def test_embed(self):
        """
        Serialized variation can have data source embedded.
        """
        # Create group
        r = self.client.post(self.uri_groups, data={'name': 'dummy'}, headers=[auth_header()])
        group = json.loads(r.data)['group']['uri']

        # Create sample
        data = {'name': 'Test sample',
                'pool_size': 1,
                'groups': [group]}
        r = self.client.post(self.uri_samples, data=json.dumps(data), content_type='application/json', headers=[auth_header(login='trader', password='test')])
        assert_equal(r.status_code, 201)
        sample = json.loads(r.data)['sample']['uri']

        # Upload VCF
        data = {'name': 'Test observations',
                'filetype': 'vcf',
                'data': open('tests/data/exome.vcf')}
        r = self.client.post(self.uri_data_sources, data=data, headers=[auth_header(login='trader', password='test')])
        assert_equal(r.status_code, 201)
        # Todo: Something better than the replace.
        vcf_data_source = r.headers['Location'].replace('http://localhost', '')

        # Import observations
        data = {'sample': sample,
                'data_source': vcf_data_source}
        r = self.client.post(self.uri_variations, data=data, headers=[auth_header(login='trader', password='test')])
        assert_equal(r.status_code, 201)
        variation = json.loads(r.data)['variation']['uri']

        # Get variation without data source embedded
        r = self.client.get(variation, headers=[auth_header(login='trader', password='test')])
        assert_equal(r.status_code, 200)
        assert 'name' not in json.loads(r.data)['variation']['data_source']

        # Get variation with data source embedded
        # Todo: http://stackoverflow.com/questions/4293460/how-to-add-custom-parameters-to-an-url-query-string-with-python
        r = self.client.get(variation + '?embed=data_source', headers=[auth_header(login='trader', password='test')])
        assert_equal(r.status_code, 200)
        assert_equal(json.loads(r.data)['variation']['data_source']['name'], 'Test observations')

    def test_trader(self):
        """
        A trader can only annotate after importing and activating.
        """
        # Create group
        r = self.client.post(self.uri_groups, data={'name': 'dummy'}, headers=[auth_header()])
        group = json.loads(r.data)['group']['uri']

        # Create sample
        data = {'name': 'Test sample',
                'pool_size': 1,
                'groups': [group]}
        r = self.client.post(self.uri_samples, data=json.dumps(data), content_type='application/json', headers=[auth_header(login='trader', password='test')])
        assert_equal(r.status_code, 201)
        sample = json.loads(r.data)['sample']['uri']

        # Upload VCF
        data = {'name': 'Test observations',
                'filetype': 'vcf',
                'data': open('tests/data/exome.vcf')}
        r = self.client.post(self.uri_data_sources, data=data, headers=[auth_header(login='trader', password='test')])
        assert_equal(r.status_code, 201)
        # Todo: Something better than the replace.
        vcf_data_source = r.headers['Location'].replace('http://localhost', '')

        # Annotate observations
        data = {'data_source': vcf_data_source, 'queries': [{'name': 'GLOBAL', 'expression': '*'}]}
        r = self.client.post(self.uri_annotations, data=json.dumps(data), content_type='application/json', headers=[auth_header(login='trader', password='test')])
        assert_equal(r.status_code, 400)

        # Import observations
        data = {'sample': sample,
                'data_source': vcf_data_source}
        r = self.client.post(self.uri_variations, data=data, headers=[auth_header(login='trader', password='test')])
        assert_equal(r.status_code, 201)
        variation = json.loads(r.data)['variation']['uri']

        # Wait for importing
        # Note: Bogus since during testing tasks return synchronously
        for _ in range(5):
            r = self.client.get(variation, headers=[auth_header(login='trader', password='test')])
            assert_equal(r.status_code, 200)
            if json.loads(r.data)['variation']['task']['done']:
                break
            time.sleep(1)
        else:
            assert False

        # Annotate observations
        data = {'data_source': vcf_data_source, 'queries': [{'name': 'GLOBAL', 'expression': '*'}]}
        r = self.client.post(self.uri_annotations, data=json.dumps(data), content_type='application/json', headers=[auth_header(login='trader', password='test')])
        assert_equal(r.status_code, 400)

        # Activate sample
        data = {'active': True}
        r = self.client.patch(sample, data=json.dumps(data), content_type='application/json', headers=[auth_header(login='trader', password='test')])
        assert_equal(r.status_code, 200)

        # Annotate observations
        data = {'data_source': vcf_data_source, 'queries': [{'name': 'GLOBAL', 'expression': '*'}]}
        r = self.client.post(self.uri_annotations, data=json.dumps(data), content_type='application/json', headers=[auth_header(login='trader', password='test')])
        assert_equal(r.status_code, 201)

    def _annotate(self, vcf_data_source, queries=None):
        """
        Annotate observations and return the annotated data source URI.
        """
        queries = queries or []

        # Annotate observations
        data = {'data_source': vcf_data_source,
                'queries': [{'name': 'Q%s' % (i + 1), 'expression': query}
                            for i, query in enumerate(queries)]}
        r = self.client.post(self.uri_annotations, data=json.dumps(data), content_type='application/json', headers=[auth_header()])
        assert_equal(r.status_code, 201)
        annotation = json.loads(r.data)['annotation']['uri']

        # Wait for writing
        # Note: Bogus since during testing tasks return synchronously
        for _ in range(5):
            r = self.client.get(annotation, headers=[auth_header()])
            assert_equal(r.status_code, 200)
            if json.loads(r.data)['annotation']['task']['done']:
                break
            time.sleep(1)
        else:
            assert False

        # Get annotated data source URI
        r = self.client.get(annotation, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        return json.loads(r.data)['annotation']['annotated_data_source']['uri']

    def _import(self, name, vcf_file, bed_file=None, pool_size=1):
        """
        Import observations and coverage. Return a tuple with URIs for the
        sample, VCF data source, and BED data source.
        """
        # Create group
        r = self.client.post(self.uri_groups, data={'name': 'dummy'}, headers=[auth_header()])
        group = json.loads(r.data)['group']['uri']

        # Create sample
        data = {'name': name,
                'coverage_profile': bed_file is not None,
                'pool_size': pool_size,
                'groups': [group]}
        r = self.client.post(self.uri_samples, data=json.dumps(data), content_type='application/json', headers=[auth_header()])
        assert_equal(r.status_code, 201)
        sample = json.loads(r.data)['sample']['uri']

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

        # Import observations
        data = {'sample': sample,
                'data_source': vcf_data_source}
        r = self.client.post(self.uri_variations, data=data, headers=[auth_header()])
        assert_equal(r.status_code, 201)
        variation = json.loads(r.data)['variation']['uri']

        # Wait for importing
        # Note: Bogus since during testing tasks return synchronously
        for _ in range(5):
            r = self.client.get(variation, headers=[auth_header()])
            assert_equal(r.status_code, 200)
            if json.loads(r.data)['variation']['task']['done']:
                break
            time.sleep(1)
        else:
            assert False

        # Import regions
        if bed_data_source:
            data = {'sample': sample,
                    'data_source': bed_data_source}
            r = self.client.post(self.uri_coverages, data=data, headers=[auth_header()])
            assert_equal(r.status_code, 201)
            coverage = json.loads(r.data)['coverage']['uri']

            # Wait for importing
            # Note: Bogus since during testing tasks return synchronously
            for _ in range(5):
                r = self.client.get(coverage, headers=[auth_header()])
                assert_equal(r.status_code, 200)
                if json.loads(r.data)['coverage']['task']['done']:
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
        sample = json.loads(r.data)['sample']['uri']

        # Upload VCF
        data = {'name': 'Some variants',
                'filetype': 'vcf',
                'data': open('tests/data/1kg.vcf')}
        r = self.client.post(self.uri_data_sources, data=data, headers=[auth_header()])
        assert_equal(r.status_code, 201)
        # Todo: Something better than the replace.
        data_source = r.headers['Location'].replace('http://localhost', '')

        # Import VCF
        data = {'sample': sample,
                'data_source': data_source}
        r = self.client.post(self.uri_variations, data=data, headers=[auth_header()])
        assert_equal(r.status_code, 201)
        wait = json.loads(r.data)['wait']

        # Check success
        r = self.client.get(wait, headers=[auth_header()])
        assert_equal(r.status_code, 200)
        ok_(json.loads(r.data)['observations']['ready'])

    def test_sample_collection(self):
        """
        List all samples.
        """
        with self.app.test_request_context():
            admin = User.query.filter_by(login='admin').one()
            db.session.add_all(Sample(admin, 'Sample %d' % i)
                               for i in range(10))
            db.session.commit()

        r = self.client.get(self.uri_samples,
                            headers=[auth_header(), ('Range', 'items=0-20')])
        assert_equal(r.status_code, 206)
        samples = json.loads(r.data)['sample_collection']['items']
        assert_equal(len(samples), 10)

    def test_sample_collection_no_range(self):
        """
        List all samples without range header.
        """
        r = self.client.get(self.uri_samples, headers=[auth_header()])
        assert_equal(r.status_code, 400)

    def test_sample_collection_first_page(self):
        """
        List first few samples.
        """
        with self.app.test_request_context():
            admin = User.query.filter_by(login='admin').one()
            db.session.add_all(Sample(admin, 'Sample %d' % i)
                               for i in range(10))
            db.session.commit()

        r = self.client.get(self.uri_samples,
                            headers=[auth_header(), ('Range', 'items=0-4')])
        assert_equal(r.status_code, 206)
        samples = json.loads(r.data)['sample_collection']['items']
        assert_equal(len(samples), 5)

    def test_sample_collection_middle_page(self):
        """
        List middle few samples.
        """
        with self.app.test_request_context():
            admin = User.query.filter_by(login='admin').one()
            db.session.add_all(Sample(admin, 'Sample %d' % i)
                               for i in range(10))
            db.session.commit()

        r = self.client.get(self.uri_samples,
                            headers=[auth_header(), ('Range', 'items=4-8')])
        assert_equal(r.status_code, 206)
        samples = json.loads(r.data)['sample_collection']['items']
        assert_equal(len(samples), 5)

    def test_sample_collection_last_page(self):
        """
        List last few samples.
        """
        with self.app.test_request_context():
            admin = User.query.filter_by(login='admin').one()
            db.session.add_all(Sample(admin, 'Sample %d' % i)
                               for i in range(10))
            db.session.commit()

        r = self.client.get(self.uri_samples,
                            headers=[auth_header(), ('Range', 'items=5-9')])
        assert_equal(r.status_code, 206)
        samples = json.loads(r.data)['sample_collection']['items']
        assert_equal(len(samples), 5)

    def test_sample_collection_no_page(self):
        """
        List nonexisting samples.
        """
        with self.app.test_request_context():
            admin = User.query.filter_by(login='admin').one()
            db.session.add_all(Sample(admin, 'Sample %d' % i)
                               for i in range(10))
            db.session.commit()

        r = self.client.get(self.uri_samples,
                            headers=[auth_header(), ('Range', 'items=80-90')])
        assert_equal(r.status_code, 416)

    def test_sample_collection_user(self):
        """
        List samples by user.
        """
        with self.app.test_request_context():
            admin = User.query.filter_by(login='admin').one()
            user = User.query.filter_by(login='user').one()

            db.session.add_all(Sample(admin, 'Sample admin %d' % i)
                               for i in range(10))
            db.session.add_all(Sample(user, 'Sample user %d' % i)
                               for i in range(10))
            db.session.commit()

            # This is a bit of a hack
            admin_uri = '/users/%d' % admin.id
            user_uri = '/users/%d' % user.id

        # All samples
        r = self.client.get(self.uri_samples,
                            headers=[auth_header(), ('Range', 'items=0-50')])
        assert_equal(r.status_code, 206)
        samples = json.loads(r.data)['sample_collection']['items']
        assert_equal(len(samples), 20)

        # Admin samples
        r = self.client.get(self.uri_samples, data={'user': admin_uri},
                            headers=[auth_header(), ('Range', 'items=0-50')])
        assert_equal(r.status_code, 206)
        samples = json.loads(r.data)['sample_collection']['items']
        assert_equal(len(samples), 10)
        for sample in samples:
            assert sample['name'].startswith('Sample admin ')

        # User samples
        r = self.client.get(self.uri_samples, data={'user': user_uri},
                            headers=[auth_header(), ('Range', 'items=0-50')])
        assert_equal(r.status_code, 206)
        samples = json.loads(r.data)['sample_collection']['items']
        assert_equal(len(samples), 10)
        for sample in samples:
            assert sample['name'].startswith('Sample user ')

    def test_sample_collection_groups(self):
        """
        List samples by groups.
        """
        with self.app.test_request_context():
            admin = User.query.filter_by(login='admin').one()
            group_a = Group('Group A')
            group_b = Group('Group B')

            db.session.add(group_a)
            db.session.add(group_b)
            db.session.add_all(Sample(admin, 'Sample A %d' % i, groups=[group_a])
                               for i in range(10))
            db.session.add_all(Sample(admin, 'Sample B %d' % i, groups=[group_b])
                               for i in range(10))
            db.session.add_all(Sample(admin, 'Sample AB %d' % i, groups=[group_a, group_b])
                               for i in range(10))
            db.session.commit()

            # This is a bit of a hack
            group_a_uri = '/groups/%d' % group_a.id
            group_b_uri = '/groups/%d' % group_b.id

        # All samples
        r = self.client.get(self.uri_samples,
                            headers=[auth_header(), ('Range', 'items=0-50')])
        assert_equal(r.status_code, 206)
        samples = json.loads(r.data)['sample_collection']['items']
        assert_equal(len(samples), 30)

        # Group A samples
        r = self.client.get(self.uri_samples, data={'groups': group_a_uri},
                            headers=[auth_header(), ('Range', 'items=0-50')])
        assert_equal(r.status_code, 206)
        samples = json.loads(r.data)['sample_collection']['items']
        assert_equal(len(samples), 20)
        for sample in samples:
            assert sample['name'].startswith('Sample A ') or sample['name'].startswith('Sample AB')

        # Group B samples
        r = self.client.get(self.uri_samples, data={'groups': group_b_uri},
                            headers=[auth_header(), ('Range', 'items=0-50')])
        assert_equal(r.status_code, 206)
        samples = json.loads(r.data)['sample_collection']['items']
        assert_equal(len(samples), 20)
        for sample in samples:
            assert sample['name'].startswith('Sample B ') or sample['name'].startswith('Sample AB')
