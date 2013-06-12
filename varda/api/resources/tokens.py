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
    Authentication tokens for users.
    """
    model = Token
    instance_name = 'token'
    instance_type = 'token'

    embeddable = {'user': UsersResource}
    filterable = {'user': 'user'}
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
    @require_basic_auth
    def list_view(cls, *args, **kwargs):
        """
        Get a collection of tokens.
        """
        return super(TokensResource, cls).list_view(*args, **kwargs)

    @classmethod
    @require_basic_auth
    def get_view(cls, *args, **kwargs):
        """
        Get token details.
        """
        return super(TokensResource, cls).get_view(*args, **kwargs)

    @classmethod
    @require_basic_auth
    def add_view(cls, **kwargs):
        """
        Create a token.
        """
        return super(TokensResource, cls).add_view(**kwargs)

    @classmethod
    @require_basic_auth
    def edit_view(cls, *args, **kwargs):
        """
        Update a token.
        """
        return super(TokensResource, cls).edit_view(*args, **kwargs)

    @classmethod
    def delete_view(cls, *args, **kwargs):
        """
        Delete a token.
        """
        return super(TokensResource, cls).delete_view(*args, **kwargs)

    @classmethod
    def serialize(cls, instance, embed=None):
        serialization = super(TokensResource, cls).serialize(instance, embed=embed)
        serialization.update(name=instance.name,
                             key=instance.key,
                             added=str(instance.added.isoformat()))
        return serialization
