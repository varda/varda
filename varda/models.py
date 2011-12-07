"""
Models backed by SQL using SQLAlchemy.

Todo: Perhaps add some delete cascade rules.
"""


import os
import gzip
import uuid
from datetime import date
from contextlib import closing

import bcrypt
from sqlalchemy import Index

from varda import app, db
from varda.region_binning import assign_bin


# Todo: Use the types for which we have validators
DATA_SOURCE_FILETYPES = ('bed', 'vcf', 'annotation')

# Note: Add new roles at the end
USER_ROLES = ('admin', 'importer')


class InvalidDataSource(Exception):
    """
    Exception thrown if data source validation failed.
    """
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super(Exception, self).__init__(code, message)

    def to_dict(self):
        return {'code':    self.code,
                'message': self.message}


class DataUnavailable(Exception):
    """
    Exception thrown if reading from a data source which data is not cached
    anymore (in case of local storage) or does not exist anymore (in case of
    a URL resource.
    """
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super(Exception, self).__init__(code, message)

    def to_dict(self):
        return {'code':    self.code,
                'message': self.message}


class User(db.Model):
    """
    User in the system.

    For the roles column we use a bitstring where the leftmost role in the
    USER_ROLES tuple is defined by the least-significant bit. Essentially,
    this creates a set of roles.

    Todo: The bitstring encoding/decoding can probably be implemented more
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
        return '<User %s identified by %s added %s>' % (self.name, self.login, str(self.added))

    def to_dict(self):
        return {'id':       self.id,
                'name':     self.name,
                'login':    self.login,
                'added':    str(self.added)}

    def check_password(self, password):
        return bcrypt.hashpw(password, self.password_hash) == self.password_hash

    def roles(self):
        """
        Todo: If we choose Python 2.7, use {'admin'} set syntax
        """
        return set(role for i, role in enumerate(USER_ROLES)
                   if self.roles_bitstring & pow(2, i))


class DataSource(db.Model):
    """
    Data source (probably uploaded as a file). E.g. VCF file to be imported, or
    BED track from which Region entries are created.

    Todo: We can now provide data as an uploaded file or as a path to a local
        file. We also want to be able to give a link to a internet resource.
    """
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    filename = db.Column(db.String(50))
    filetype = db.Column(db.Enum(*DATA_SOURCE_FILETYPES, name='filetype'))
    gzipped = db.Column(db.Boolean)
    added = db.Column(db.Date)

    def __init__(self, name, filetype, upload=None, local_path=None, gzipped=False):
        if not filetype in DATA_SOURCE_FILETYPES:
            raise InvalidDataSource('unknown_filetype', 'Data source filetype is unknown')

        self.name = name
        self.filename = str(uuid.uuid4())
        self.filetype = filetype
        self.gzipped = gzipped
        self.added = date.today()

        filepath = os.path.join(app.config['FILES_DIR'], self.filename)

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

        if not self.is_valid():
            os.unlink(filepath)
            raise InvalidDataSource('invalid_data', 'Data source cannot be read')

    def __repr__(self):
        return '<DataSource %s as %s added %s>' % (self.name, self.filetype, str(self.added))

    def to_dict(self):
        return {'id':       self.id,
                'name':     self.name,
                'filetype': self.filetype,
                'gzipped':  self.gzipped,
                'added':    str(self.added)}

    def data(self):
        """
        Be sure to close after calling this.
        """
        filepath = os.path.join(app.config['FILES_DIR'], self.filename)
        try:
            if self.gzipped:
                # Todo: The closing wrapper is not needed in Python 2.7
                return closing(gzip.open(filepath))
            else:
                open(filepath)
        except EnvironmentError:
            raise DataUnavailable('data_source_not_cached', 'Data source is not in the cache')

    def local_path(self):
        """
        Get a local filepath for the data.
        """
        return os.path.join(app.config['FILES_DIR'], self.filename)

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


class Annotation(db.Model):
    """
    Annotated data source.
    """
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}

    id = db.Column(db.Integer, primary_key=True)
    data_source_id = db.Column(db.Integer, db.ForeignKey('data_source.id'))
    filename = db.Column(db.String(50))
    added = db.Column(db.Date)

    data_source = db.relationship(DataSource, backref=db.backref('annotations', lazy='dynamic'))

    def __init__(self, data_source):
        self.data_source = data_source
        self.filename = str(uuid.uuid4())
        self.added = date.today()

    def __repr__(self):
        return '<Annotation for %r added %s>' % (self.data_source, str(self.added))

    def to_dict(self):
        return {'id':          self.id,
                'data_source': self.data_source_id,
                'gzipped':     self.gzipped,
                'added':       str(self.added)}

    def data(self):
        """
        Be sure to close after calling this.
        """
        filepath = os.path.join(app.config['FILES_DIR'], self.filename)
        # Todo: The closing wrapper is not needed in Python 2.7
        return closing(gzip.open(filepath))

    def data_writer(self):
        """
        Be sure to close after calling this.
        """
        filepath = os.path.join(app.config['FILES_DIR'], self.filename)
        # Todo: The closing wrapper is not needed in Python 2.7
        return closing(gzip.open(filepath, 'wb'))

    def local_path(self):
        """
        Get a local filepath for the data.
        """
        return os.path.join(app.config['FILES_DIR'], self.filename)


class Variant(db.Model):
    """
    Genomic variant.
    """
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}

    id = db.Column(db.Integer, primary_key=True)
    chromosome = db.Column(db.String(2))
    begin = db.Column(db.Integer)
    end = db.Column(db.Integer)
    reference = db.Column(db.String(200))
    variant = db.Column(db.String(200))

    def __init__(self, chromosome, begin, end, reference, variant):
        self.chromosome = chromosome
        self.begin = begin
        self.end = end
        self.reference = reference
        self.variant = variant

    def __repr__(self):
        return '<Variant %s at chr%s:%i-%i>' % (
            self.variant, self.chromosome, self.begin, self.end)

    def to_dict(self):
        return {'id':         self.id,
                'chromosome': self.chromosome,
                'begin':      self.begin,
                'end':        self.end,
                'reference':  self.reference,
                'variant':    self.variant}


Index('index_variant_position',
      Variant.chromosome, Variant.begin, Variant.end)
Index('index_variant_unique',
      Variant.chromosome, Variant.begin, Variant.end,
      Variant.reference, Variant.variant, unique=True)


class Sample(db.Model):
    """
    Sample.
    """
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    coverage_threshold = db.Column(db.Integer)
    pool_size = db.Column(db.Integer)
    added = db.Column(db.Date)

    def __init__(self, name, coverage_threshold=8, pool_size=1):
        self.name = name
        self.coverage_threshold = coverage_threshold
        self.pool_size = pool_size
        self.added = date.today()

    def __repr__(self):
        return '<Sample %s of %i>' % (self.name, self.pool_size)

    def to_dict(self):
        return {'id':                 self.id,
                'name':               self.name,
                'coverage_threshold': self.coverage_threshold,
                'pool_size':          self.pool_size,
                'added':              str(self.added)}


class Observation(db.Model):
    """
    Observation in a sample.

    Note: For pooled samples (or population studies), a combination of
        (sample_id, variant_id) may not be unique. So this cannot make the
        primary key (as we previously had).
        SQLAlchemy is not happy if we have no primary key at all, so we add
        an id column.
    """
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}

    id = db.Column(db.Integer, primary_key=True)
    sample_id = db.Column(db.Integer, db.ForeignKey('sample.id'))
    variant_id = db.Column(db.Integer, db.ForeignKey('variant.id'))
    data_source_id = db.Column(db.Integer, db.ForeignKey('data_source.id'))

    # Depending on the type of sample, the following 3 fields may or not
    # have data. If we have no data, we store None.
    total_coverage = db.Column(db.Integer)
    variant_coverage = db.Column(db.Integer)
    support = db.Column(db.Integer)  # Number of individuals for pooled sample

    sample = db.relationship(Sample, backref=db.backref('observations', lazy='dynamic'))
    variant = db.relationship(Variant, backref=db.backref('observations', lazy='dynamic'))
    data_source = db.relationship(DataSource, backref=db.backref('observations', lazy='dynamic'))

    def __init__(self, sample, variant, data_source, total_coverage=None, variant_coverage=None, support=None):
        self.sample = sample
        self.variant = variant
        self.data_source = data_source
        self.total_coverage = total_coverage
        self.variant_coverage = variant_coverage
        self.support = support

    def __repr__(self):
        return '<Observation %r on %r>' % (self.variant, self.sample)

    def to_dict(self):
        return {'sample':           self.sample.id,
                'variant':          self.variant.id,
                'data_source':      self.data_source.id,
                'total_coverage':   self.total_coverage,
                'variant_coverage': self.variant_coverage,
                'support':          self.support}


class Region(db.Model):
    """
    Covered region for a sample.
    """
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}

    id = db.Column(db.Integer, primary_key=True)
    sample_id = db.Column(db.Integer, db.ForeignKey('sample.id'))
    data_source_id = db.Column(db.Integer, db.ForeignKey('data_source.id'))
    chromosome = db.Column(db.String(2))
    begin = db.Column(db.Integer)
    end = db.Column(db.Integer)
    bin = db.Column(db.Integer)

    sample = db.relationship(Sample, backref=db.backref('regions', lazy='dynamic'))
    data_source = db.relationship(DataSource, backref=db.backref('regions', lazy='dynamic'))

    def __init__(self, sample, data_source, chromosome, begin, end):
        self.sample = sample
        self.data_source = data_source
        self.chromosome = chromosome
        self.begin = begin
        self.end = end
        self.bin = assign_bin(self.begin, self.end)

    def __repr__(self):
        return '<Region for %r at chr%s:%i-%i>' % (self.sample, self.chromosome, self.begin, self.end)

    def to_dict(self):
        return {'sample':      self.sample.id,
                'data_source': self.data_source.id,
                'chromosome':  self.chromosome,
                'begin':       self.begin,
                'end':         self.end}


Index('region_begin',
      Region.chromosome, Region.begin)
Index('region_end',
      Region.chromosome, Region.end)
