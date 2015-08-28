"""
Varda management console.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


import argparse
import getpass
import os
import sys

from sqlalchemy.orm.exc import NoResultFound

from . import create_app, db
from .models import User


def debugserver(args):
    """
    Run a local server in debug mode.
    """
    # Note that we cannot use the Werkzeug reloader here, since it uses
    # `sys.argv` to start a new instance. When using
    # `python -m varda.bin.debugserver`, Python sets rewrites `sys.argv` to
    # the full path of the `.py` file (instead of `-m` and the module name).
    app = create_app()

    if args.setup:
        database_setup(app, alembic_config=args.alembic_config,
                       destructive=args.destructive,
                       admin_password_hash=args.admin_password_hash)

    app.run(debug=True, use_reloader=False)


def setup(args):
    """
    Setup the database and admin user.
    """
    database_setup(create_app(), alembic_config=args.alembic_config,
                   destructive=args.destructive,
                   admin_password_hash=args.admin_password_hash)


def database_setup(app, alembic_config='alembic.ini', destructive=False,
                   admin_password_hash=None):
    if not os.path.isfile(alembic_config):
        sys.stderr.write('Cannot find Alembic configuration: %s\n'
                         % alembic_config)
        sys.exit(1)

    with app.app_context():
        if destructive:
            db.drop_all()

        if destructive or not db.engine.has_table(User.__tablename__):
            # We assume our migrations will take care of everything if at
            # least the User table eists.
            db.create_all()

        admin_setup(password_hash=admin_password_hash)

        import alembic.command
        import alembic.config
        from alembic.migration import MigrationContext

        context = MigrationContext.configure(db.session.connection())
        if destructive or context.get_current_revision() is None:
            # We need to close the current session before running Alembic.
            db.session.remove()
            alembic_config = alembic.config.Config(alembic_config)
            alembic.command.stamp(alembic_config, 'head')


def admin_setup(password_hash=None):
    """
    Update the password for the admin user. If the admin user does not exist,
    it is created.

    If `password_hash` is not specified, the user is queried for the new
    password interactively.
    """
    password = None

    if not password_hash:
        password = getpass.getpass('Please provide a password for the admin '
                                   'user: ')
        password_control = getpass.getpass('Repeat: ')

        if password != password_control:
            sys.stderr.write('Passwords did not match\n')
            sys.exit(1)

    try:
        admin = User.query.filter_by(login='admin').one()
        if password_hash:
            admin.password_hash = password_hash
        else:
            admin.password = password
    except NoResultFound:
        admin = User('Admin User', 'admin', password=password,
                     password_hash=password_hash, roles=['admin'])
        db.session.add(admin)

    db.session.commit()


def main():
    """
    Management console.
    """
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument('--alembic-config', metavar='ALEMBIC_CONFIG',
                               dest='alembic_config', help='path to alembic '
                               'configuration file (default: alembic.ini)',
                               default='alembic.ini')
    config_parser.add_argument('--destructive', dest='destructive',
                               action='store_true', help='delete any '
                               'existing tables and data before running setup')
    config_parser.add_argument('--admin-password', metavar='BCRYPT_HASH',
                               dest='admin_password_hash', help='use this '
                               'bcrypt hash instead of querying for the admin '
                               'password interactively')

    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                     parents=[config_parser])
    subparsers = parser.add_subparsers(title='subcommands', dest='subcommand',
                                       help='subcommand help')

    p = subparsers.add_parser('debugserver', help=debugserver.__doc__,
                              parents=[config_parser])
    p.add_argument('-s', '--setup', dest='setup', action='store_true',
                   help='run setup first')
    p.set_defaults(func=debugserver)

    p = subparsers.add_parser('setup', help=setup.__doc__,
                              parents=[config_parser])
    p.set_defaults(func=setup)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
