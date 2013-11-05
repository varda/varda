"""Add CSV file format

Revision ID: 52c2d8ff8e6f
Revises: 5880ee6542b
Create Date: 2013-11-05 13:10:48.463890

"""

# revision identifiers, used by Alembic.
revision = '52c2d8ff8e6f'
down_revision = '5880ee6542b'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # In PostgreSQL < 9.1 there was no ALTER TYPE for enums, so it would have
    # been something like:
    #
    #     ALTER TABLE foo ALTER COLUMN bar TYPE new_type USING bar::text::new_type;
    #
    # However, all my installations are PostgreSQL >= 9.1 and I think the USING
    # syntax is PostgreSQL-specific, so let's ignore that. It would also come
    # with all the hassle of moving old column values into the new column.
    context = op.get_context()
    if context.bind.dialect.name == 'postgresql':
        if context.bind.dialect.server_version_info >= (9, 3):
            op.execute('COMMIT')
            op.execute("ALTER TYPE filetype ADD VALUE IF NOT EXISTS 'csv'")
            return
        if context.bind.dialect.server_version_info >= (9, 1):
            op.execute('COMMIT')
            op.execute("ALTER TYPE filetype ADD VALUE 'csv'")
            return
    raise Exception('Sorry, only PostgreSQL >= 9.1 is supported by this migration')


def downgrade():
    pass
