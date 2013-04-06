"""
Varda management console.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


import argparse
import getpass
import os
import sys

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
        database_setup(app, alembic_config=args.alembic_config)

    app.run(debug=True, use_reloader=False)


def setup(args):
    """
    Setup the database (destructive).
    """
    database_setup(create_app(), alembic_config=args.alembic_config)


def database_setup(app, alembic_config='alembic.ini'):
    if not os.path.isfile(alembic_config):
        sys.stderr.write('Cannot find Alembic configuration: %s\n'
                         % alembic_config)
        sys.exit(1)

    admin_password = getpass.getpass('Please provide a password for the admin user: ')
    admin_password_control = getpass.getpass('Repeat: ')

    if admin_password != admin_password_control:
        sys.stderr.write('Passwords did not match\n')
        sys.exit(1)

    with app.app_context():
        db.drop_all()
        db.create_all()

        import alembic.command
        import alembic.config
        alembic_config = alembic.config.Config(alembic_config)
        alembic.command.stamp(alembic_config, 'head')

        admin = User('Admin User', 'admin', admin_password, roles=['admin'])
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
