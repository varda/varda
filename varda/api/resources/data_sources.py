"""
REST API data sources resource.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from flask import current_app, g, request, send_from_directory, url_for

from ...models import DataSource, DATA_SOURCE_FILETYPES
from ..security import is_user, has_role, owns_data_source
from .base import Resource


class DataSourcesResource(Resource):
    """
    A data source is represented as an object with the following fields:

    * **uri** (`string`) - URI for this data source.
    * **user_uri** (`string`) - URI for the data source :ref:`owner <api_users>`.
    * **data_uri** (`string`) - URI for the data.
    * **name** (`string`) - Human readable name.
    * **filetype** (`string`) - Data filetype.
    * **gzipped** (`boolean`) - Whether or not data is compressed.
    * **added** (`string`) - Date this data source was added.
    """
    model = DataSource
    instance_name = 'data_source'
    instance_type = 'data_source'

    views = ['list', 'get', 'add', 'edit', 'data']

    filterable = {'user': 'user'}

    list_ensure_conditions = [has_role('admin'), is_user]
    list_ensure_options = {'satisfy': any}

    get_ensure_conditions = [has_role('admin'), owns_data_source]
    get_ensure_options = {'satisfy': any}

    add_ensure_conditions = []
    add_schema = {'name': {'type': 'string', 'required': True},
                  'filetype': {'type': 'string', 'allowed': DATA_SOURCE_FILETYPES,
                               'required': True},
                  'gzipped': {'type': 'boolean'},
                  'local_path': {'type': 'string'}}

    edit_schema = {'name': {'type': 'string'}}

    data_rule = '/<int:data_source>/data'
    data_ensure_conditions = [has_role('admin'), owns_data_source]
    data_ensure_options = {'satisfy': any}
    data_schema = {'data_source': {'type': 'data_source'}}

    def register_views(self):
        super(DataSourcesResource, self).register_views()
        if 'data' in self.views:
            self.register_view('data')

    @classmethod
    def add_view(cls, **kwargs):
        # Todo: If files['data'] is missing (or non-existent file?), we crash with
        #     a data_source_not_cached error.
        # Todo: Sandbox local_path (per user).
        # Todo: Option to upload the actual data later at the /data_source/XX/data
        #     endpoint, symmetrical to the GET request.
        kwargs.update(user=g.user, upload=request.files.get('data'))
        return super(DataSourcesResource, cls).add_view(**kwargs)

    @classmethod
    def data_view(cls, data_source):
        return send_from_directory(current_app.config['FILES_DIR'],
                                   data_source.filename,
                                   mimetype='application/x-gzip')

    @classmethod
    def serialize(cls, instance, embed=None):
        serialization = super(DataSourcesResource, cls).serialize(instance, embed=embed)
        serialization.update(user_uri=url_for('.user_get', user=instance.user.id),
                             data_uri=url_for('.data_source_data', data_source=instance.id),
                             name=instance.name,
                             filetype=instance.filetype,
                             gzipped=instance.gzipped,
                             added=str(instance.added.isoformat()))
        return serialization
