"""
REST API data sources model resource.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from flask import current_app, g, request, send_from_directory, url_for

from ...models import DataSource, DATA_SOURCE_FILETYPES
from ..security import has_role, is_user, owns_data_source, require_user
from .base import ModelResource
from .users import UsersResource


class DataSourcesResource(ModelResource):
    """
    Data source resources model data from files that are either uploaded to
    the server by the user or generated on the server.

    The actual data is modeled by the :ref:`blob
    <api-resources-data-sources-blobs>` subresource type.
    """
    model = DataSource
    instance_name = 'data_source'
    instance_type = 'data_source'

    views = ['list', 'get', 'add', 'edit', 'delete', 'data']

    embeddable = {'user': UsersResource}
    filterable = {'user': 'user'}
    orderable = ['name', 'filetype', 'added']

    list_ensure_conditions = [has_role('admin'), is_user]
    list_ensure_options = {'satisfy': any}

    get_ensure_conditions = [has_role('admin'), owns_data_source]
    get_ensure_options = {'satisfy': any}

    add_ensure_conditions = []
    add_schema = {'name': {'type': 'string', 'maxlength': 200, 'required': True},
                  'filetype': {'type': 'string', 'allowed': DATA_SOURCE_FILETYPES,
                               'required': True},
                  'gzipped': {'type': 'boolean'},
                  'local_file': {'type': 'string', 'maxlength': 200}}

    edit_ensure_conditions = [has_role('admin'), owns_data_source]
    edit_ensure_options = {'satisfy': any}
    edit_schema = {'name': {'type': 'string', 'maxlength': 200}}

    data_rule = '/<int:data_source>/data'
    data_ensure_conditions = [has_role('admin'), owns_data_source]
    data_ensure_options = {'satisfy': any}
    data_schema = {'data_source': {'type': 'data_source', 'id': True}}

    def register_views(self):
        super(DataSourcesResource, self).register_views()
        if 'data' in self.views:
            self.register_view('data')

    @classmethod
    def serialize(cls, instance, embed=None):
        """
        A data source is represented as an object with the following fields:

        **uri** (`uri`)
          URI for this resource.

        **added** (`string`)
          Date and time this sample was added, see :ref:`api-datetime`.

        **gzipped** (`boolean`)
          Whether or not the data is compressed using gzip.

        **name** (`string`)
          Human readable data source name.

        **filetype** (`string`)
          Data filetype. Possible values for this field are `bed`, `vcf`, and
          `csv`.

        **data** (`object`)
          :ref:`Link <api-links>` to a :ref:`blob
          <api-resources-data-sources-blobs>` resource.

        **user** (`object`)
          :ref:`Link <api-links>` to a :ref:`user
          <api-resources-users-instances>` resource (embeddable).
        """
        serialization = super(DataSourcesResource, cls).serialize(instance, embed=embed)
        serialization.update(data={'uri': url_for('.data_source_data',
                                                  data_source=instance.id)},
                             name=instance.name,
                             filetype=instance.filetype,
                             gzipped=instance.gzipped,
                             added=str(instance.added.isoformat()))
        return serialization

    @classmethod
    def list_view(cls, *args, **kwargs):
        """
        Returns a collection of data sources in the `data_source_collection`
        field.

        .. note:: Requires having the `admin` role or being the user specified
           by the `user` filter.

        **Available filters:**

        - **user** (`uri`)

        **Orderable by:** `name`, `filetype`, `added`
        """
        return super(DataSourcesResource, cls).list_view(*args, **kwargs)

    @classmethod
    def get_view(cls, *args, **kwargs):
        """
        Returns the data source representation in the `data_source` field.

        .. note:: Requires having the `admin` role or being the owner of the
           data source.
        """
        return super(DataSourcesResource, cls).get_view(*args, **kwargs)

    @classmethod
    @require_user
    def add_view(cls, *args, **kwargs):
        """
        Adds a data source resource.

        .. note:: Requires :ref:`user authentication <api-authentication>`.

        **Required request data:**

        - **name** (`string`)
        - **filetype** (`string`)

        **Accepted request data:**

        - **gzipped** (`boolean`)
        - **local_file** (`string`)
        - **data** (`file`)
        """
        # Todo: If files['data'] is missing (or non-existent file?), we crash with
        #     a data_source_not_cached error.
        # Todo: Sandbox local_path (per user).
        # Todo: Option to upload the actual data later at the /data_source/XX/data
        #     endpoint, symmetrical to the GET request.
        # Todo: Is it possible to call this without authentication?
        kwargs.update(user=g.user, upload=request.files.get('data'))
        return super(DataSourcesResource, cls).add_view(*args, **kwargs)

    @classmethod
    def edit_view(cls, *args, **kwargs):
        """
        Updates a data source resource.

        .. note:: Requires having the `admin` role or being the owner of the
           data source.

        **Accepted request data:**

        - **name** (`string`)
        """
        return super(DataSourcesResource, cls).edit_view(*args, **kwargs)

    @classmethod
    def data_view(cls, data_source):
        """
        Returns the gzipped data source data.

        .. warning:: The response body will not be a JSON document.

        .. note:: Requires having the `admin` role or being the owner of the
           data source.
        """
        return send_from_directory(current_app.config['DATA_DIR'],
                                   data_source.filename,
                                   mimetype='application/x-gzip')
