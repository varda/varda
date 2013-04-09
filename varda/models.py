"""
Models backed by SQL using SQLAlchemy.

Note that all genomic positions in this module are one-based and inclusive.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. todo:: Perhaps add some delete cascade rules.

.. Licensed under the MIT license, see the LICENSE file.
"""


from datetime import datetime
import gzip
import os
import uuid

import bcrypt
from flask import current_app
from sqlalchemy import Index
from sqlalchemy.orm.exc import DetachedInstanceError
import werkzeug

from . import db
from .region_binning import assign_bin


# Todo: Use the types for which we have validators.
DATA_SOURCE_FILETYPES = ('bed', 'vcf')

OBSERVATION_ZYGOSITIES = ('heterozygous', 'homozygous')

# Note: Add new roles at the end.
USER_ROLES = (
    'admin',       # Can do anything.
    'importer',    # Can import samples.
    'annotator',   # Can annotate samples.
    'trader'       # Can annotate samples if they are also imported.
)


class InvalidDataSource(Exception):
    """
    Exception thrown if data source validation failed.
    """
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super(InvalidDataSource, self).__init__(code, message)


class DataUnavailable(Exception):
    """
    Exception thrown if reading from a data source which data is not cached
    anymore (in case of local storage) or does not exist anymore (in case of
    a URL resource.
    """
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super(DataUnavailable, self).__init__(code, message)


class User(db.Model):
    """
    User in the system.

    For the roles column we use a bitstring where the leftmost role in the
    :data:`USER_ROLES` tuple is defined by the least-significant bit.
    Essentially, this creates a set of roles.

    .. todo:: The bitstring encoding/decoding can probably be implemented more
        efficiently.
    """
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    login = db.Column(db.String(40), index=True, unique=True)
    password_hash = db.Column(db.String(100))
    email = db.Column(db.String(200))
    roles_bitstring = db.Column(db.Integer)
    added = db.Column(db.DateTime)

    def __init__(self, name, login, password, email=None, roles=None):
        roles = roles or []
        self.name = name
        self.login = login
        self.password_hash = bcrypt.hashpw(password, bcrypt.gensalt())
        self.email = email
        self.roles_bitstring = sum(pow(2, i) for i, role
                                   in enumerate(USER_ROLES) if role in roles)
        self.added = datetime.now()

    def __repr__(self):
        return 'User(%r, %r, %r, %r)' % (self.name, self.login, '***',
                                         list(self.roles))

    def check_password(self, password):
        return (bcrypt.hashpw(password, self.password_hash) ==
                self.password_hash)

    @property
    def roles(self):
        return {role for i, role in enumerate(USER_ROLES)
                if self.roles_bitstring & pow(2, i)}


class Sample(db.Model):
    """
    Sample.

    ``coverage_profile`` is essentially ``not is_population_study`` and should
    always be True iff the sample has one or more Coverage entries (so perhaps
    we should not store it, but have it as a calculated property).
    """
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}

    # Todo: Should we have a unique constraint on (user_id, name)?

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    name = db.Column(db.String(200))
    pool_size = db.Column(db.Integer)
    added = db.Column(db.DateTime)
    active = db.Column(db.Boolean, default=False)
    coverage_profile = db.Column(db.Boolean)
    public = db.Column(db.Boolean)
    notes = db.Column(db.Text)

    user = db.relationship(User,
                           backref=db.backref('samples', lazy='dynamic'))

    def __init__(self, user, name, pool_size=1, coverage_profile=True,
                 public=False, notes=None):
        self.user = user
        self.name = name
        self.pool_size = pool_size
        self.added = datetime.now()
        self.coverage_profile = coverage_profile
        self.public = public
        self.notes = notes

    def __repr__(self):
        return '<Sample "%s" of %d individuals added %s>' % (self.name,
                                                             self.pool_size,
                                                             str(self.added))


class DataSource(db.Model):
    """
    Data source (probably uploaded as a file). E.g. VCF file to be imported,
    or BED track from which Region entries are created.

    .. note:: Data source checksums are not forced to be unique, since several
        users might upload the same data source and do different things with
        it.
    """
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    name = db.Column(db.String(200))
    filename = db.Column(db.String(50))
    filetype = db.Column(db.Enum(*DATA_SOURCE_FILETYPES, name='filetype'))
    gzipped = db.Column(db.Boolean)
    added = db.Column(db.DateTime)
    checksum = db.Column(db.String(40))
    records = db.Column(db.Integer)

    user = db.relationship(User,
                           backref=db.backref('data_sources', lazy='dynamic'))

    def __init__(self, user, name, filetype, upload=None, local_file=None,
                 empty=False, gzipped=False):
        if not filetype in DATA_SOURCE_FILETYPES:
            raise InvalidDataSource('unknown_filetype',
                                    'Data source filetype "%s" is unknown'
                                    % filetype)

        self.user = user
        self.name = name
        self.filename = str(uuid.uuid4())
        self.filetype = filetype
        self.gzipped = gzipped
        self.added = datetime.now()

        path = os.path.join(current_app.config['DATA_DIR'],
                                self.filename)

        if upload is not None:
            if gzipped:
                upload.save(path)
            else:
                data = gzip.open(path, 'wb')
                data.write(upload.read())
                data.close()
            self.gzipped = True
        elif local_file is not None:
            if not current_app.config['SECONDARY_DATA_DIR']:
                raise InvalidDataSource(
                    'invalid_data', 'Referencing local data files is not '
                    'allowed by system configuration')
            if current_app.config['SECONDARY_DATA_BY_USER']:
                local_dir = os.path.join(current_app.config['SECONDARY_DATA_DIR'],
                                         user.login)
            else:
                local_dir = current_app.config['SECONDARY_DATA_DIR']
            local_path = os.path.join(local_dir,
                                      werkzeug.secure_filename(local_file))
            if not os.path.isfile(local_path):
                raise InvalidDataSource(
                    'invalid_data', 'Local data file referenced does not exist')
            os.symlink(local_path, path)
        elif not empty:
            raise InvalidDataSource('invalid_data', 'No data supplied')

    def __repr__(self):
        # Todo: If CELERY_ALWAYS_EAGER=True, the worker can end up with a
        #     detached session when printing its log after an error. This
        #     is a hacky workaround, we might implement it as a decorator
        #     on the __repr__ method or the model itself, but it will still
        #     be a hack. I think this is something that could be fixed in
        #     celery itself.
        try:
            return '<DataSource "%s" as %s added %s>' % (self.name,
                                                         self.filetype,
                                                         str(self.added))
        except DetachedInstanceError:
            return '<DataSource ...>'

    def data(self):
        """
        Get open file-like handle to data contained in this data source for
        reading.

        .. note:: Be sure to close after calling this.
        """
        filepath = os.path.join(current_app.config['DATA_DIR'],
                                self.filename)
        try:
            if self.gzipped:
                return gzip.open(filepath)
            else:
                return open(filepath)
        except EnvironmentError:
            raise DataUnavailable('data_source_not_cached',
                                  'Data source is not in the cache')

    def data_writer(self):
        """
        Get open file-like handle to data contained in this data source for
        writing.

        .. note:: Be sure to close after calling this.
        """
        filepath = os.path.join(current_app.config['DATA_DIR'],
                                self.filename)
        try:
            if self.gzipped:
                return gzip.open(filepath, 'wb')
            else:
                return open(filepath, 'wb')
        except EnvironmentError:
            raise DataUnavailable('data_source_not_cached',
                                  'Data source is not in the cache')

    def empty(self):
        """
        Remove all data from this data source.
        """
        with self.data_writer():
            pass

    def local_path(self):
        """
        Get a local filepath for the data.
        """
        return os.path.join(current_app.config['DATA_DIR'], self.filename)


class Variation(db.Model):
    """
    Coupling between a Sample, a DataSource, and Observations.
    """
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}

    id = db.Column(db.Integer, primary_key=True)
    sample_id = db.Column(db.Integer, db.ForeignKey('sample.id'))
    data_source_id = db.Column(db.Integer, db.ForeignKey('data_source.id'))
    task_done = db.Column(db.Boolean, default=False)
    task_uuid = db.Column(db.String(36))
    skip_filtered = db.Column(db.Boolean)
    use_genotypes = db.Column(db.Boolean)
    prefer_genotype_likelihoods = db.Column(db.Boolean)

    sample = db.relationship(Sample,
                             backref=db.backref('variations', lazy='dynamic'))
    data_source = db.relationship(DataSource,
                                  backref=db.backref('variations',
                                                     lazy='dynamic'))

    def __init__(self, sample, data_source, skip_filtered=True,
                 use_genotypes=True, prefer_genotype_likelihoods=False):
        self.sample = sample
        self.data_source = data_source
        self.skip_filtered = skip_filtered
        self.use_genotypes = use_genotypes
        self.prefer_genotype_likelihoods = prefer_genotype_likelihoods

    def __repr__(self):
        return '<Variation>'
        #return '<Variation "%d", %simported>' % (
        #    self.id, '' if self.task_done else 'not ')


class Coverage(db.Model):
    """
    Coupling between a Sample, a DataSource, and Regions.
    """
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}

    id = db.Column(db.Integer, primary_key=True)
    sample_id = db.Column(db.Integer, db.ForeignKey('sample.id'))
    data_source_id = db.Column(db.Integer, db.ForeignKey('data_source.id'))
    task_done = db.Column(db.Boolean, default=False)
    task_uuid = db.Column(db.String(36))

    sample = db.relationship(Sample,
                             backref=db.backref('coverages', lazy='dynamic'))
    data_source = db.relationship(DataSource,
                                  backref=db.backref('coverages',
                                                     lazy='dynamic'))

    def __init__(self, sample, data_source):
        self.sample = sample
        self.data_source = data_source

    def __repr__(self):
        return '<Coverage "%d", %simported>' % (
            self.id, '' if self.task_done else 'not ')


sample_frequency = db.Table(
    'sample_frequency', db.Model.metadata,
    db.Column('annotation_id', db.Integer, db.ForeignKey('annotation.id')),
    db.Column('sample_id', db.Integer, db.ForeignKey('sample.id')))


class Annotation(db.Model):
    """
    Annotated data source.
    """
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}

    id = db.Column(db.Integer, primary_key=True)
    original_data_source_id = db.Column(db.Integer,
                                        db.ForeignKey('data_source.id'))
    annotated_data_source_id = db.Column(db.Integer,
                                         db.ForeignKey('data_source.id'))
    task_done = db.Column(db.Boolean, default=False)
    task_uuid = db.Column(db.String(36))
    global_frequency = db.Column(db.Boolean)

    original_data_source = db.relationship(
        DataSource,
        primaryjoin='DataSource.id==Annotation.original_data_source_id',
        backref=db.backref('annotations', lazy='dynamic'))
    annotated_data_source = db.relationship(
        DataSource,
        primaryjoin='DataSource.id==Annotation.annotated_data_source_id',
        backref=db.backref('annotation', uselist=False, lazy='select'))

    sample_frequency = db.relationship(Sample, secondary=sample_frequency)

    def __init__(self, original_data_source, annotated_data_source,
                 global_frequency=True, sample_frequency=None):
        sample_frequency = sample_frequency or []

        self.original_data_source = original_data_source
        self.annotated_data_source = annotated_data_source
        self.global_frequency = global_frequency
        self.sample_frequency = sample_frequency

    # Todo: Never use self.id in the repr, we might not have it yet.
    def __repr__(self):
        return '<Annotation "%d", %swritten>' % (
            self.id, '' if self.task_done else 'not ')


class Observation(db.Model):
    """
    Observation in a sample.
    """
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}

    id = db.Column(db.Integer, primary_key=True)
    variation_id = db.Column(db.Integer, db.ForeignKey('variation.id'),
                             index=True)

    chromosome = db.Column(db.String(30))
    position = db.Column(db.Integer)
    reference = db.Column(db.String(200))
    observed = db.Column(db.String(200))
    bin = db.Column(db.Integer)

    # Todo: Should we perhaps also store the end position? Would make it
    #     easier to query for variants overlapping some position. Perhaps it's
    #     enough to have a computed index for len(referenc)?
    #     If we actually store begin-end, it's actually a range, and it would
    #     be clearer how to store insertions unambiguously.

    # A zygosity of ``None`` means exact genotype is unknown, but the variant
    # allele was observed.
    zygosity = db.Column(db.Enum(*OBSERVATION_ZYGOSITIES, name='zygosity'))

    # Number of individuals.
    support = db.Column(db.Integer)

    variation = db.relationship(Variation,
                                backref=db.backref('observations',
                                                   lazy='dynamic'))

    def __init__(self, variation, chromosome, position, reference, observed,
                 zygosity=None, support=1):
        self.variation = variation
        self.chromosome = chromosome
        self.position = position
        self.reference = reference
        self.observed = observed
        # We choose the 'region' of the reference covered by an insertion to
        # be the base next to it.
        self.bin = assign_bin(self.position,
                              self.position + max(1, len(self.reference)) - 1)
        self.zygosity = zygosity
        self.support = support

    def __repr__(self):
        return 'Observation<%r, %r, %r, %r>' % (
            self.chromosome, self.position, self.reference, self.observed)

    def is_deletion(self):
        return self.observed == ''

    def is_insertion(self):
        return self.reference == ''

    def is_snv(self):
        return len(self.observed) == len(self.reference) == 1

    def is_indel(self):
        return not (self.is_deletion() or
                    self.is_insertion() or
                    self.is_snv())


Index('observation_location',
      Observation.bin, Observation.chromosome, Observation.position)


class Region(db.Model):
    """
    Covered region for a sample.
    """
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}

    id = db.Column(db.Integer, primary_key=True)
    coverage_id = db.Column(db.Integer, db.ForeignKey('coverage.id'),
                            index=True)
    chromosome = db.Column(db.String(30))
    begin = db.Column(db.Integer)
    end = db.Column(db.Integer)
    bin = db.Column(db.Integer)

    # Todo: Perhaps we might want to have a `support` column here similar to
    #     the Observation model? It only makes sense if we accept BED files
    #     with a `support` integer for each region.

    coverage = db.relationship(Coverage,
                               backref=db.backref('regions', lazy='dynamic'))

    def __init__(self, coverage, chromosome, begin, end):
        self.coverage = coverage
        self.chromosome = chromosome
        self.begin = begin
        self.end = end
        self.bin = assign_bin(self.begin, self.end)

    def __repr__(self):
        return '<Region chr%s:%i-%i>' % (self.chromosome, self.begin,
                                         self.end)


Index('region_location',
      Region.bin, Region.chromosome, Region.begin)
