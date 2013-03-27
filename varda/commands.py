"""
Varda management console.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


import argparse
import getpass
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
    create_app().run(debug=True, use_reloader=False)


def setup(args):
    """
    Setup the database (destructive).
    """
    app = create_app()

    admin_password = getpass.getpass('Please provide a password for the admin user: ')
    admin_password_control = getpass.getpass('Repeat: ')

    if admin_password != admin_password_control:
        sys.stderr.write('Passwords did not match\n')
        sys.exit(1)

    with app.app_context():
        db.drop_all()
        db.create_all()
        admin = User('Admin User', 'admin', admin_password, roles=['admin'])
        db.session.add(admin)
        db.session.commit()


def main():
    """
    Management console.
    """
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    subparsers = parser.add_subparsers(title='subcommands', dest='subcommand',
                                       help='subcommand help')

    p = subparsers.add_parser('debugserver', help=debugserver.__doc__)
    p.set_defaults(func=debugserver)

    p = subparsers.add_parser('setup', help=setup.__doc__)
    p.set_defaults(func=setup)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
