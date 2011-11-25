"""
Models backed by SQL using SQLAlchemy.
"""


from datetime import date

from sqlalchemy import Index

from varda import db


class Variant(db.Model):
    """
    Genomic variant.
    """
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
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    pool_size = db.Column(db.Integer)
    added = db.Column(db.Date)

    def __init__(self, name, pool_size=1):
        self.name = name
        self.pool_size = pool_size
        self.added = date.today()

    def __repr__(self):
        return '<Sample %s of %i>' % (self.name, self.pool_size)

    def to_dict(self):
        return {'id':        self.id,
                'name':      self.name,
                'pool_size': self.pool_size,
                'added':     str(self.added)}


class Observation(db.Model):
    """
    Observation in a sample
    """
    sample_id = db.Column(db.Integer, db.ForeignKey('sample.id'), primary_key=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('variant.id'), primary_key=True)

    # Depending on the type of sample, the following 3 fields may or not
    # have data. If we have no data, we store None.
    total_coverage = db.Column(db.Integer)
    variant_coverage = db.Column(db.Integer)
    support = db.Column(db.Integer)  # Number of individuals for pooled sample

    sample = db.relationship(Sample, backref=db.backref('observations', lazy='dynamic'))
    variant = db.relationship(Variant, backref=db.backref('observations', lazy='dynamic'))

    def __init__(self, sample, variant, total_coverage=None, variant_coverage=None, support=None):
        self.sample = sample
        self.variant = variant
        self.total_coverage = total_coverage
        self.variant_coverage = variant_coverage
        self.support = support

    def __repr__(self):
        return '<Observation %r on %r>' % (self.variant, self.sample)

    def to_dict(self):
        return {'sample':           self.sample.id,
                'variant':          self.variant.id,
                'total_coverage':   self.total_coverage,
                'variant_coverage': self.variant_coverage,
                'support':          self.support}


class Region(db.Model):
    """
    Covered region for a sample.
    """
    id = db.Column(db.Integer, primary_key=True)
    sample_id = db.Column(db.Integer, db.ForeignKey('sample.id'), primary_key=True)
    chromosome = db.Column(db.String(2))
    begin = db.Column(db.Integer)
    end = db.Column(db.Integer)
    bin = db.Column(db.Integer)

    sample = db.relationship(Sample, backref=db.backref('regions', lazy='dynamic'))

    def __init__(self, sample, chromosome, begin, end):
        self.sample = sample
        self.chromosome = chromosome
        self.begin = begin
        self.end = end
        self.bin = 14  # Todo

    def __repr__(self):
        return '<Region for %r at chr%s:%i-%i>' % (self.sample, self.chromosome, self.begin, self.end)

    def to_dict(self):
        return {'sample':     self.sample.id,
                'chromosome': self.chromosome,
                'begin':      self.begin,
                'end':        self.end}


Index('region_begin',
      Region.chromosome, Region.begin)
Index('region_end',
      Region.chromosome, Region.end)


class DataSource(db.Model):
    """
    Data source (probably uploaded as a file). E.g. VCF file to be iported, or
    a list of variants to be annotated.
    """
    id = db.Column(db.Integer, primary_key=True)
    added = db.Column(db.Date)

    def __init__(self):
        self.added = date.today()

    def __repr__(self):
        return '<DataSource added %s>' % str(self.added)

    def to_dict(self):
        return {'id':    self.id,
                'added': str(self.added)}
