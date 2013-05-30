"""Cascade deletes on annotation, coverage, variation

Revision ID: 13ba676ea0cf
Revises: d23512f46a2
Create Date: 2013-05-30 17:17:04.331830

"""

# revision identifiers, used by Alembic.
revision = '13ba676ea0cf'
down_revision = 'd23512f46a2'

from alembic import op
import sqlalchemy as sa


foreign_keys = [('sample_frequency', 'annotation'),
                ('observation', 'variation'),
                ('region', 'coverage')]


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
            op.create_foreign_key(fk['name'], source, referent, [referent + '_id'], ['id'])
