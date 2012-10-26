"""
Models backed by SQL using SQLAlchemy.

Note that all genomic positions in this module are one-based and inclusive.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. todo:: Perhaps add some delete cascade rules.

.. Licensed under the MIT license, see the LICENSE file.
"""


from datetime import date
import gzip
import os
import uuid

from flask import current_app
from sqlalchemy import Index
from sqlalchemy.orm.exc import DetachedInstanceError
import bcrypt

from . import db
from .region_binning import assign_bin


DATA_SOURCE_FILETYPES = ('bed', 'vcf')
"""
.. todo:: Use the types for which we have validators.
"""

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

    .. todo:: Login should really be validated to only contain alphanums.
    .. todo:: The bitstring encoding/decoding can probably be implemented more
        efficiently.
    """
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    login = db.Column(db.String(200), index=True, unique=True)
    password_hash = db.Column(db.String(200))
    roles_bitstring = db.Column(db.Integer)
    added = db.Column(db.Date)

    def __init__(self, name, login, password, roles=[]):
        self.name = name
        self.login = login
        self.password_hash = bcrypt.hashpw(password, bcrypt.gensalt())
        self.roles_bitstring = sum(pow(2, i) for i, role in enumerate(USER_ROLES)
                                   if role in roles)
        self.added = date.today()

    def __repr__(self):
        return 'User(%r, %r, %r, %r)' % (self.name, self.login, '***', list(self.roles))

    def check_password(self, password):
        return bcrypt.hashpw(password, self.password_hash) == self.password_hash

    @property
    def roles(self):
        return {role for i, role in enumerate(USER_ROLES)
                if self.roles_bitstring & pow(2, i)}


class Variant(db.Model):
    """
    Genomic variant.
    """
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}

    id = db.Column(db.Integer, primary_key=True)
    chromosome = db.Column(db.String(30))
    begin = db.Column(db.Integer)
    end = db.Column(db.Integer)
    reference = db.Column(db.String(200))
    variant = db.Column(db.String(200))
    bin = db.Column(db.Integer)

    def __init__(self, chromosome, begin, end, reference, variant):
        self.chromosome = chromosome
        self.begin = begin
        self.end = end
        self.reference = reference
        self.variant = variant
        self.bin = assign_bin(self.begin, self.end)

    def __repr__(self):
        return 'Variant(%r, %r, %r, %r, %r)' % (
            self.chromosome, self.begin, self.end, self.reference, self.variant)


Index('variant_location',
      Variant.chromosome, Variant.begin)
Index('variant_unique',
      Variant.chromosome, Variant.begin, Variant.end,
      Variant.reference, Variant.variant, unique=True)


class Sample(db.Model):
    """
    Sample.

    ``coverage_profile`` is essentially ``not is_population_study``.
    """
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    name = db.Column(db.String(200))
    pool_size = db.Column(db.Integer)
    added = db.Column(db.Date)
    active = db.Column(db.Boolean, default=False)
    coverage_profile = db.Column(db.Boolean)
    public = db.Column(db.Boolean)

    user = db.relationship(User, backref=db.backref('samples', lazy='dynamic'))

    def __init__(self, user, name, pool_size=1, coverage_profile=True, public=False):
        self.user = user
        self.name = name
        self.pool_size = pool_size
        self.added = date.today()
        self.coverage_profile = coverage_profile
        self.public = public

    def __repr__(self):
        return '<Sample "%s" of %d individuals added %s>' % (self.name, self.pool_size, str(self.added))


class DataSource(db.Model):
    """
    Data source (probably uploaded as a file). E.g. VCF file to be imported, or
    BED track from which Region entries are created.

    .. todo:: We can now provide data as an uploaded file or as a path to a
        local file. We also want to be able to give a link to an internet
        resource.

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
    added = db.Column(db.Date)
    checksum = db.Column(db.String(40))
    records = db.Column(db.Integer)

    user = db.relationship(User, backref=db.backref('data_sources', lazy='dynamic'))

    def __init__(self, user, name, filetype, upload=None, local_path=None, empty=False, gzipped=False):
        if not filetype in DATA_SOURCE_FILETYPES:
            raise InvalidDataSource('unknown_filetype', 'Data source filetype is unknown')

        self.user = user
        self.name = name
        self.filename = str(uuid.uuid4())
        self.filetype = filetype
        self.gzipped = gzipped
        self.added = date.today()

        filepath = os.path.join(current_app.config['FILES_DIR'], self.filename)

        if upload is not None:
            if gzipped:
                upload.save(filepath)
            else:
                data = gzip.open(filepath, 'wb')
                data.write(upload.read())
                data.close()
            self.gzipped = True
        elif local_path is not None:
            os.symlink(local_path, filepath)

        if not empty and not self.is_valid():
            os.unlink(filepath)
            raise InvalidDataSource('invalid_data', 'Data source cannot be read')

    def __repr__(self):
        # Todo: If CELERY_ALWAYS_EAGER=True, the worker can end up with a
        #     detached session when printing its log after an error. This
        #     is a hacky workaround, we might implement it as a decorator
        #     on the __repr__ method or the model itself, but it will still
        #     be a hack. I think this is something that could be fixed in
        #     celery itself.
        try:
            return '<DataSource "%s" as %s added %s>' % (self.name, self.filetype, str(self.added))
        except DetachedInstanceError:
            return '<DataSource ...>'

    def data(self):
        """
        Get open file-like handle to data contained in this data source for
        reading.

        .. note:: Be sure to close after calling this.
        """
        filepath = os.path.join(current_app.config['FILES_DIR'], self.filename)
        try:
            if self.gzipped:
                return gzip.open(filepath)
            else:
                return open(filepath)
        except EnvironmentError:
            raise DataUnavailable('data_source_not_cached', 'Data source is not in the cache')

    def data_writer(self):
        """
        Get open file-like handle to data contained in this data source for
        writing.

        .. note:: Be sure to close after calling this.
        """
        filepath = os.path.join(current_app.config['FILES_DIR'], self.filename)
        try:
            if self.gzipped:
                return gzip.open(filepath, 'wb')
            else:
                return open(filepath, 'wb')
        except EnvironmentError:
            raise DataUnavailable('data_source_not_cached', 'Data source is not in the cache')

    def local_path(self):
        """
        Get a local filepath for the data.
        """
        return os.path.join(current_app.config['FILES_DIR'], self.filename)

    def is_valid(self):
        """
        Peek into the file and determine if it is of the given filetype.
        """
        data = self.data()

        def is_bed():
            # Todo.
            return True

        def is_vcf():
            return 'fileformat=VCFv4.1' in data.readline()

        validators = {'bed': is_bed,
                      'vcf': is_vcf}
        with data as data:
            return validators[self.filetype]()


class Variation(db.Model):
    """
    Coupling between a Sample, a DataSource, and Observations.
    """
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}

    id = db.Column(db.Integer, primary_key=True)
    sample_id = db.Column(db.Integer, db.ForeignKey('sample.id'))
    data_source_id = db.Column(db.Integer, db.ForeignKey('data_source.id'))
    imported = db.Column(db.Boolean, default=False)
    import_task_uuid = db.Column(db.String(36))

    sample = db.relationship(Sample, backref=db.backref('variations', lazy='dynamic'))
    data_source = db.relationship(DataSource, backref=db.backref('variations', lazy='dynamic'))

    def __init__(self, sample, data_source):
        self.sample = sample
        self.data_source = data_source

    def __repr__(self):
        return '<Variation ...>'


class Coverage(db.Model):
    """
    Coupling between a Sample, a DataSource, and Regions.
    """
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}

    id = db.Column(db.Integer, primary_key=True)
    sample_id = db.Column(db.Integer, db.ForeignKey('sample.id'))
    data_source_id = db.Column(db.Integer, db.ForeignKey('data_source.id'))
    imported = db.Column(db.Boolean, default=False)
    import_task_uuid = db.Column(db.String(36))

    sample = db.relationship(Sample, backref=db.backref('coverages', lazy='dynamic'))
    data_source = db.relationship(DataSource, backref=db.backref('coverages', lazy='dynamic'))

    def __init__(self, sample, data_source):
        self.sample = sample
        self.data_source = data_source

    def __repr__(self):
        return '<Coverage ...>'


class Annotation(db.Model):
    """
    Annotated data source.
    """
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}

    id = db.Column(db.Integer, primary_key=True)
    original_data_source_id = db.Column(db.Integer, db.ForeignKey('data_source.id'))
    annotated_data_source_id = db.Column(db.Integer, db.ForeignKey('data_source.id'))
    written = db.Column(db.Boolean, default=False)
    write_task_uuid = db.Column(db.String(36))

    original_data_source = db.relationship(DataSource, primaryjoin='DataSource.id==Annotation.original_data_source_id', backref=db.backref('annotations', lazy='dynamic'))
    annotated_data_source = db.relationship(DataSource, primaryjoin='DataSource.id==Annotation.annotated_data_source_id', backref=db.backref('annotation', uselist=False, lazy='dynamic'))

    def __init__(self, original_data_source, annotated_data_source):
        self.original_data_source = original_data_source
        self.annotated_data_source = annotated_data_source

    def __repr__(self):
        return '<Annotation ...>'


class Observation(db.Model):
    """
    Observation in a sample.
    """
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}

    id = db.Column(db.Integer, primary_key=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('variant.id'))
    variation_id = db.Column(db.Integer, db.ForeignKey('variation.id'))

    # Number of individuals.
    support = db.Column(db.Integer)

    variant = db.relationship(Variant, backref=db.backref('observations', lazy='dynamic'))
    variation = db.relationship(Variation, backref=db.backref('observations', lazy='dynamic'))

    def __init__(self, variant, variation, support=1):
        self.variant = variant
        self.variation = variation
        self.support = support

    def __repr__(self):
        return '<Observation ...>'


class Region(db.Model):
    """
    Covered region for a sample.
    """
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}

    id = db.Column(db.Integer, primary_key=True)
    coverage_id = db.Column(db.Integer, db.ForeignKey('coverage.id'))
    chromosome = db.Column(db.String(30))
    begin = db.Column(db.Integer)
    end = db.Column(db.Integer)
    bin = db.Column(db.Integer)

    coverage = db.relationship(Coverage, backref=db.backref('regions', lazy='dynamic'))

    def __init__(self, coverage, chromosome, begin, end):
        self.coverage = coverage
        self.chromosome = chromosome
        self.begin = begin
        self.end = end
        self.bin = assign_bin(self.begin, self.end)

    def __repr__(self):
        return '<Region chr%s:%i-%i>' % (self.chromosome, self.begin, self.end)


Index('region_location',
      Region.bin, Region.chromosome, Region.begin)
