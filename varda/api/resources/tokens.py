"""
REST API tokens model resource.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from flask import g

from ...models import Token
from ..security import has_role, is_user, owns_token, require_basic_auth
from .base import ModelResource
from .users import UsersResource


class TokensResource(ModelResource):
    """
    Token resources model :ref:`authentication tokens
    <api-authentication-token>` for API users.
    """
    model = Token
    instance_name = 'token'
    instance_type = 'token'

    embeddable = {'user': UsersResource}
    filterable = {'user': {'type': 'user'}}
    orderable = ['name', 'added']

    list_ensure_conditions = [has_role('admin'), is_user]
    list_ensure_options = {'satisfy': any}

    get_ensure_conditions = [has_role('admin'), owns_token]
    get_ensure_options = {'satisfy': any}

    add_ensure_conditions = [has_role('admin'), is_user]
    add_ensure_options = {'satisfy': any}
    add_schema = {'user': {'type': 'user', 'required': True},
                  'name': {'type': 'string', 'maxlength': 200, 'required': True}}

    edit_ensure_conditions = [has_role('admin'), owns_token]
    edit_ensure_options = {'satisfy': any}
    edit_schema = {'name': {'type': 'string', 'maxlength': 200}}

    delete_ensure_conditions = [has_role('admin'), owns_token]
    delete_ensure_options = {'satisfy': any}

    @classmethod
    def serialize(cls, instance, embed=None):
        """
        A token is represented as an object with the following fields:

        **uri** (`uri`)
          URI for this resource.

        **added** (`string`)
          Date and time this sample was added, see :ref:`api-datetime`.

        **key** (`string`)
          Token key used for authentication.

        **name** (`string`)
          Human readable sample name.

        **user** (`object`)
          :ref:`Link <api-links>` to a :ref:`user
          <api-resources-users-instances>` resource (embeddable).
        """
        serialization = super(TokensResource, cls).serialize(instance, embed=embed)
        serialization.update(name=instance.name,
                             key=instance.key,
                             added=str(instance.added.isoformat()))
        return serialization

    @classmethod
    @require_basic_auth
    def list_view(cls, *args, **kwargs):
        """
        Returns a collection of tokens in the `collection` field.

        .. note:: Requires having the `admin` role or being the user specified
           by the `user` filter.

        .. note:: This request is only allowed using :ref:`HTTP Basic
           Authentication <api-authentication-basic>`, not token
           authentication.

        **Available filters:**

        - **user** (`uri`)

        **Orderable by:** `name`, `added`
        """
        return super(TokensResource, cls).list_view(*args, **kwargs)

    @classmethod
    @require_basic_auth
    def get_view(cls, *args, **kwargs):
        """
        Returns the token representation in the `token` field.

        .. note:: Requires having the `admin` role or being the owner of the
           token.

        .. note:: This request is only allowed using :ref:`HTTP Basic
           Authentication <api-authentication-basic>`, not token
           authentication.
        """
        return super(TokensResource, cls).get_view(*args, **kwargs)

    @classmethod
    @require_basic_auth
    def add_view(cls, *args, **kwargs):
        """
        Adds a token resource.

        .. note:: Requires having the `admin` or being the user specified by
           the `user` data field.

        .. note:: This request is only allowed using :ref:`HTTP Basic
           Authentication <api-authentication-basic>`, not token
           authentication.

        **Required request data:**

        - **user** (`uri`)
        - **name** (`string`)
        """
        return super(TokensResource, cls).add_view(*args, **kwargs)

    @classmethod
    @require_basic_auth
    def edit_view(cls, *args, **kwargs):
        """
        Updates a token resource.

        .. note:: Requires having the `admin` role or being the owner of the
           token.

        .. note:: This request is only allowed using :ref:`HTTP Basic
           Authentication <api-authentication-basic>`, not token
           authentication.

        **Accepted request data:**

        - **name** (`string`)
        """
        return super(TokensResource, cls).edit_view(*args, **kwargs)

    @classmethod
    def delete_view(cls, *args, **kwargs):
        """
        Todo: documentation, including how/if we cascade.
        """
        return super(TokensResource, cls).delete_view(*args, **kwargs)
