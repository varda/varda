"""Cascade delete on sample

Revision ID: 5880ee6542b
Revises: 13ba676ea0cf
Create Date: 2013-05-31 09:17:39.833072

"""

# revision identifiers, used by Alembic.
revision = '5880ee6542b'
down_revision = '13ba676ea0cf'

from alembic import op
import sqlalchemy as sa


foreign_keys = [('coverage', 'sample'),
                ('variation', 'sample'),
                ('sample_frequency', 'sample')]


def upgrade():
    from sqlalchemy.engine.reflection import Inspector
    insp = Inspector.from_engine(op.get_bind())

    for source, referent in foreign_keys:
        fks = insp.get_foreign_keys(source)
        for fk in fks:
            if fk['constrained_columns'] != [referent + '_id']:
                continue
            op.drop_constraint(fk['name'], source)
            op.create_foreign_key(fk['name'], source, referent, [referent + '_id'], ['id'], ondelete='CASCADE')


def downgrade():
    from sqlalchemy.engine.reflection import Inspector
    insp = Inspector.from_engine(op.get_bind())

    for source, referent in foreign_keys:
        fks = insp.get_foreign_keys(source)
        for fk in fks:
            if fk['constrained_columns'] != [referent + '_id']:
                continue
            op.drop_constraint(fk['name'], source)
            op.create_foreign_key(fk['name'], source, referent, [referent + '_id'], ['id'], ondelete='CASCADE')
