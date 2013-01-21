"""
REST API users resource.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from ...models import User, USER_ROLES
from ..errors import ValidationError
from ..security import is_user, has_role
from .base import Resource


class UsersResource(Resource):
    """
    A user is represented as an object with the following fields:

    * **uri** (`string`) - URI for this user.
    * **name** (`string`) - Human readable name.
    * **login** (`string`) - User login used for identification.
    * **roles** (`list of string`) - Roles this user has.
    * **added** (`string`) - Date and time this user was added.
    """
    model = User
    instance_name = 'user'
    instance_type = 'user'

    get_ensure_conditions = [has_role('admin'), is_user]
    get_ensure_options = {'satisfy': any}

    add_schema = {'login': {'type': 'string', 'minlength': 3, 'maxlength': 40,
                            'safe': True, 'required': True},
                  'name': {'type': 'string'},
                  'password': {'type': 'string', 'required': True},
                  'roles': {'type': 'list', 'allowed': USER_ROLES}}

    edit_schema = {'name': {'type': 'string'},
                   'password': {'type': 'string'},
                   'roles': {'type': 'list', 'allowed': USER_ROLES}}

    def list_view(self, *args, **kwargs):
        """
        Collection of registered users.

        .. todo:: Document what it means to be a collection of resources.

        Requires the `admin` role.

        :statuscode 200: Respond with a list of :ref:`user <api_users>` objects
            as `users`.

        Example request:

        .. sourcecode:: http

            GET /users HTTP/1.1

        Example response:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
              "users":
                [
                  {
                    "uri": "/users/1",
                    "name": "Frederick Sanger",
                    "login": "fred",
                    "roles": ["admin"],
                    "added": "2012-11-23T10:55:12.776706"
                  },
                  {
                    "uri": "/users/2",
                    "name": "Walter Gilbert",
                    "login": "walter",
                    "roles": ["importer", "annotator"],
                    "added": "2012-11-23T10:55:12.776706"
                  }
                ]
            }
        """
        return super(UsersResource, self).list_view(*args, **kwargs)

    def get_view(self, *args, **kwargs):
        """
        Details for user.

        Requires the `admin` role or being the requested user.

        :statuscode 200: Respond with a :ref:`user <api_users>` object as `user`.

        Example request:

        .. sourcecode:: http

            GET /users/1 HTTP/1.1

        Example response:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
              "user":
                {
                  "uri": "/users/1",
                  "name": "Frederick Sanger",
                  "login": "fred",
                  "roles": ["admin"],
                  "added": "2012-11-23T10:55:12.776706"
                }
            }
        """
        return super(UsersResource, self).get_view(*args, **kwargs)

    def add_view(self, **kwargs):
        """
        Create a user.

        Requires the `admin` role.

        :arg login: User login used for identification.
        :type login: string
        :arg name: Human readable name (default: `login`).
        :type name: string
        :arg password: Password.
        :type password: string
        :arg roles: Roles to assign.
        :type roles: list of string
        :statuscode 201: Respond with a URI for the created user as `user`.

        Example request:

        .. sourcecode:: http

            POST /users HTTP/1.1
            Content-Type: application/json

            {
              "name": "Paul Berg",
              "login": "paul",
              "password": "dna",
              "roles": ["importer"]
            }

        Example response:

        .. sourcecode:: http

            HTTP/1.1 201 CREATED
            Location: https://example.com/users/3
            Content-Type: application/json

            {
              "user_uri": "/users/3"
            }
        """
        login = kwargs.get('login')
        kwargs['name'] = kwargs.get('name', login)
        if User.query.filter_by(login=login).first() is not None:
            raise ValidationError('User login is not unique')
        return super(UsersResource, self).add_view(**kwargs)

    # Todo: Document that all fields are optional.
    def edit_view(self, *args, **kwargs):
        """
        Update a user.

        Requires the `admin` role.

        :arg name: Human readable name.
        :type name: string
        :arg password: Password.
        :type password: string
        :arg roles: Roles to assign.
        :type roles: list of string
        :statuscode 200: Respond with a :ref:`user <api_users>` object as
            `user`.

        Example request:

        .. sourcecode:: http

            PATCH /users/3 HTTP/1.1
            Content-Type: application/json

            {
              "name": "Changed H. Name",
              "password": "and password too"
            }

        Example response:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
              "user":
                {
                  "uri": "/users/1",
                  "name": "Changed H. Name",
                  "login": "fred",
                  "roles": ["admin"],
                  "added": "2012-11-23T10:55:12.776706"
                }
            }

        """
        return super(UsersResource, self).edit_view(*args, **kwargs)

    def serialize(self, resource, embed=None):
        serialization = super(UsersResource, self).serialize(resource, embed=embed)
        serialization.update(name=resource.name,
                             login=resource.login,
                             roles=list(resource.roles),
                             added=str(resource.added.isoformat()))
        return serialization
