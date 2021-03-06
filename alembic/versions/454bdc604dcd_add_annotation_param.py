"""Add annotation parameters

Revision ID: 454bdc604dcd
Revises: 1e6d5f30aa47
Create Date: 2013-03-14 15:37:16.410175

"""

# revision identifiers, used by Alembic.
revision = '454bdc604dcd'
down_revision = '1e6d5f30aa47'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('exclude',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('annotation_id', sa.Integer(), nullable=True),
    sa.Column('sample_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['annotation_id'], ['annotation.id'], ),
    sa.ForeignKeyConstraint(['sample_id'], ['sample.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('local_frequency',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('annotation_id', sa.Integer(), nullable=True),
    sa.Column('sample_id', sa.Integer(), nullable=True),
    sa.Column('label', sa.String(length=200), nullable=True),
    sa.ForeignKeyConstraint(['annotation_id'], ['annotation.id'], ),
    sa.ForeignKeyConstraint(['sample_id'], ['sample.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column(u'annotation', sa.Column('global_frequencies', sa.Boolean(), nullable=True))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column(u'annotation', 'global_frequencies')
    op.drop_table('local_frequency')
    op.drop_table('exclude')
    ### end Alembic commands ###
