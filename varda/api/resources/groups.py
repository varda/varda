"""
REST API groups model resource.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from ...models import Group
from ..security import has_role
from .base import ModelResource


class GroupsResource(ModelResource):
    """
    Group resources model sample groups (e.g., disease type).
    """
    model = Group
    instance_name = 'group'
    instance_type = 'group'

    views = ['list', 'get', 'add', 'edit', 'delete']

    orderable = ['name']

    list_ensure_conditions = []

    get_ensure_conditions = []

    add_ensure_conditions = [has_role('admin'), has_role('importer')]
    add_ensure_options = {'satisfy': any}
    add_schema = {'name': {'type': 'string', 'required': True, 'maxlength': 200}}

    edit_ensure_conditions = [has_role('admin')]
    edit_schema = {'name': {'type': 'string', 'required': True, 'maxlength': 200}}

    delete_ensure_conditions = [has_role('admin')]

    @classmethod
    def serialize(cls, instance, embed=None):
        """
        A group is representend as an object with the following fields:

        **uri** (`uri`)
          URI for this resource.

        **name** (`string`)
          Human readable group name.
        """
        serialization = super(GroupsResource, cls).serialize(instance, embed=embed)
        serialization.update(name=instance.name)
        return serialization

    @classmethod
    def list_view(cls, *args, **kwargs):
        """
        Returns a colleciton of groups in the `group_collection` field.
        """
        return super(GroupsResource, cls).list_view(*args, **kwargs)

    @classmethod
    def get_view(cls, *args, **kwargs):
        """
        Returns the group representation in the `group` field.
        """
        return super(GroupsResource, cls).get_view(*args, **kwargs)

    @classmethod
    def add_view(cls, *args, **kwargs):
        """
        Adds a group resource.

        .. note:: Requires having the `admin` or `importer` role.
        """
        return super(GroupsResource, cls).add_view(*args, **kwargs)

    @classmethod
    def edit_view(cls, *args, **kwargs):
        """
        Updates a group resource.

        .. note:: Requires having the `admin` role.
        """
        return super(GroupsResource, cls).edit_view(*args, **kwargs)

    @classmethod
    def delete_view(cls, *args, **kwargs):
        """
        Deletes a group resource.

        .. note:: Requires having the `admin` role.
        """
        return super(GroupsResource, cls).delete_view(*args, **kwargs)
