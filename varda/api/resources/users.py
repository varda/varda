"""
REST API users model resource.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from flask import abort, g

from ...models import User, USER_ROLES
from ..errors import ValidationError
from ..security import is_user, has_role, require_basic_auth
from .base import ModelResource


class UsersResource(ModelResource):
    """
    User resources model API users and their permissions.
    """
    model = User
    instance_name = 'user'
    instance_type = 'user'

    views = ['list', 'get', 'add', 'edit', 'delete']

    orderable = ['name', 'added']

    get_ensure_conditions = [has_role('admin'), is_user]
    get_ensure_options = {'satisfy': any}

    # Todo: I think we can lose the 'safe' constraint.
    add_schema = {'login': {'type': 'string', 'minlength': 3, 'maxlength': 40,
                            'safe': True, 'required': True},
                  'name': {'type': 'string', 'maxlength': 200},
                  'password': {'type': 'string', 'required': True, 'maxlength': 500},
                  'email': {'type': 'string', 'maxlength': 200},
                  'roles': {'type': 'list', 'allowed': USER_ROLES}}

    edit_ensure_conditions = [has_role('admin'), is_user]
    edit_ensure_options = {'satisfy': any}
    edit_schema = {'name': {'type': 'string', 'maxlength': 200},
                   'password': {'type': 'string', 'maxlength': 500},
                   'email': {'type': 'string', 'maxlength': 200},
                   'roles': {'type': 'list', 'allowed': USER_ROLES}}

    delete_ensure_conditions = [has_role('admin'), is_user]
    delete_ensure_options = {'satisfy': any}

    @classmethod
    def serialize(cls, instance, embed=None):
        """
        A user is represented as an object with the following fields:

        **uri** (`uri`)
          URI for this resource.

        **added** (`string`)
          Date and time this user was added, see :ref:`api-datetime`.

        **email** (`string`)
          User e-mail address.

        **login** (`string`)
          Login name used for authentication.

        **name** (`string`)
          Human readable user name.

        **roles** (`list` of `string`)
          Roles for this user. Possible values for this field are `admin`,
          `importer`, `annotator`, and `trader`.
        """
        serialization = super(UsersResource, cls).serialize(instance, embed=embed)
        serialization.update(name=instance.name,
                             login=instance.login,
                             email=instance.email,
                             roles=list(instance.roles),
                             added=str(instance.added.isoformat()))
        return serialization

    @classmethod
    def list_view(cls, *args, **kwargs):
        """
        Returns a collection of users in the `user_collection` field.

        .. note:: Requires having the `admin` role.

        **Orderable by:** `name`, `added`
        """
        return super(UsersResource, cls).list_view(*args, **kwargs)

    @classmethod
    def get_view(cls, *args, **kwargs):
        """
        Returns the user representation in the `user` field.

        .. note:: Requires having the `admin` role or being the requested
           user.
        """
        return super(UsersResource, cls).get_view(*args, **kwargs)

    @classmethod
    @require_basic_auth
    def add_view(cls, *args, **kwargs):
        """
        Adds a user resource.

        .. note:: Requires having the `admin` role.

        .. note:: This request is only allowed using :ref:`HTTP Basic
           Authentication <api-authentication-basic>`, not token
           authentication.

        **Required request data:**

        - **login** (`string`)
        - **password** (`string`)

        **Accepted request data:**

        - **name** (`string`)
        - **email** (`string`)
        - **roles** (`list` of `string`)
        """
        login = kwargs.get('login')
        kwargs['name'] = kwargs.get('name', login)
        if User.query.filter_by(login=login).first() is not None:
            raise ValidationError('User login is not unique')
        return super(UsersResource, cls).add_view(*args, **kwargs)

    # Todo: Document that all fields are optional.
    @classmethod
    @require_basic_auth
    def edit_view(cls, *args, **kwargs):
        """
        Updates a user resource.

        .. note:: Requires having the `admin` role or being the requested
           user.

        .. note:: This request is only allowed using :ref:`HTTP Basic
           Authentication <api-authentication-basic>`, not token
           authentication.

        **Accepted request data:**

        - **email** (`string`)
        - **login** (`string`)
        - **name** (`string`)
        - **roles** (`list` of `string`)
        """
        if 'roles' in kwargs and 'admin' not in g.user.roles:
            # Of course we don't allow any user to change their own roles,
            # only admins can do that.
            abort(403)
        return super(UsersResource, cls).edit_view(*args, **kwargs)

    @classmethod
    @require_basic_auth
    def delete_view(cls, *args, **kwargs):
        """
        Todo: documentation, including how/if we cascade.

        .. note:: This request is only allowed using :ref:`HTTP Basic
           Authentication <api-authentication-basic>`, not token
           authentication.

        .. todo:: Document that we cascade the delete to tokens, but not to
            samples and data sources.
        """
        return super(UsersResource, cls).delete_view(*args, **kwargs)
