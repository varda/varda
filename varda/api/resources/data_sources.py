"""
REST API data sources model resource.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from flask import current_app, g, request, send_from_directory, url_for

from ...models import DataSource, DATA_SOURCE_FILETYPES
from ..security import is_user, has_role, owns_data_source
from .base import ModelResource


class DataSourcesResource(ModelResource):
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

    edit_ensure_conditions = [has_role('admin'), owns_data_source]
    edit_ensure_options = {'satisfy': any}
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
    def list_view(cls, *args, **kwargs):
        """
        Get a collection of data sources.

        Requires the `admin` role or being the user specified in the `user`
        argument.

        :arg user: If set to the URI for a user, restrict the collection to
            data sources owned by this user.
        :type user: string
        :statuscode 200: Respond with a list of :ref:`data source <api_data_sources>`
            objects as `data_sources`.

        Example request:

        .. sourcecode:: http

            GET /data_sources?user=%2Fusers%2F3 HTTP/1.1

        Example response:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
              "data_sources":
                [
                  {
                    "uri": "/data_sources/23",
                    "user_uri": "/users/3",
                    "data_uri": "/data_sources/23/data",
                    "name": "1KG chromosome 20 SNPs",
                    "filetype": "vcf",
                    "gzipped": true,
                    "added": "2012-11-23T10:55:12.776706"
                  },
                  {
                    "uri": "/data_sources/24",
                    "user_uri": "/users/3",
                    "data_uri": "/data_sources/24/data",
                    "name": "1KG chromosome 21 SNPs",
                    "filetype": "vcf",
                    "gzipped": true,
                    "added": "2012-11-23T10:57:13.776706"
                  }
                ]
            }
        """
        return super(DataSourcesResource, cls).list_view(*args, **kwargs)

    @classmethod
    def get_view(cls, *args, **kwargs):
        """
        Get details for a data source.

        Requires the `admin` role or being the owner of the requested data
        source.

        :statuscode 200: Respond with a :ref:`data source <api_data_sources>`
            object as `data_source`.

        Example request:

        .. sourcecode:: http

            GET /data_sources/23 HTTP/1.1

        Example response:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
              "data_source":
                {
                  "uri": "/data_sources/23",
                  "user_uri": "/users/1",
                  "data_uri": "/data_sources/23/data",
                  "name": "1KG chromosome 20 SNPs",
                  "filetype": "vcf",
                  "gzipped": true,
                  "added": "2012-11-23T10:55:12.776706"
                }
            }
        """
        return super(DataSourcesResource, cls).get_view(*args, **kwargs)

    @classmethod
    def add_view(cls, **kwargs):
        """
        Create a data source.

        The data should be either attached as a HTTP file upload called `data`
        or specified by the `local_path` argument.

        :arg name: Human readable name.
        :type name: string
        :arg filetype: Data filetype.
        :type filetype: string
        :arg gzipped: Whether or not data is compressed (default: ``False``).
        :type gzipped: boolean
        :arg local_path: A path to the data on the local server file system
            (optional).
        :type local_path: string
        :statuscode 201: Respond with a URI for the created data source as
            `data_source_uri`.

        Example request:

        .. sourcecode:: http

            POST /data_sources HTTP/1.1
            Content-Type: application/json

            {
              "name": "1KG chromosome 20 SNPs",
              "filetype": "vcf",
              "gzipped": true,
              "local_path": "/var/upload/users/1/1kg_snp_chr20.vcf.gz"
            }

        Example response:

        .. sourcecode:: http

            HTTP/1.1 201 CREATED
            Location: https://example.com/data_sources/23
            Content-Type: application/json

            {
              "data_source_uri": "/data_sources/23"
            }
        """
        # Todo: If files['data'] is missing (or non-existent file?), we crash with
        #     a data_source_not_cached error.
        # Todo: Sandbox local_path (per user).
        # Todo: Option to upload the actual data later at the /data_source/XX/data
        #     endpoint, symmetrical to the GET request.
        kwargs.update(user=g.user, upload=request.files.get('data'))
        return super(DataSourcesResource, cls).add_view(**kwargs)

    @classmethod
    def edit_view(cls, *args, **kwargs):
        """
        Update a data source.

        Requires the `admin` role or being the owner of the requested data
        source.

        :arg name: Human readable name.
        :type name: string

        Example request:

        .. sourcecode:: http

            PATCH /data_sources/23 HTTP/1.1
            Content-Type: application/json

            {
              "name": "1KG chromosome 20 SNP calls"
            }

        Example response:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
              "data_source":
                {
                  "uri": "/data_sources/23",
                  "user_uri": "/users/1",
                  "data_uri": "/data_sources/23/data",
                  "name": "1KG chromosome 20 SNP calls",
                  "filetype": "vcf",
                  "gzipped": true,
                  "added": "2012-11-23T10:55:12.776706"
                }
            }
        """
        return super(DataSourcesResource, cls).edit_view(*args, **kwargs)

    @classmethod
    def data_view(cls, data_source):
        """
        Get data for a data source.

        Requires the `admin` role or being the owner of the requested data source.

        :statuscode 200: Respond with the data for the data source.

        Example request:

        .. sourcecode:: http

            GET /data_sources/23/data HTTP/1.1

        Example response:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/x-gzip

            <gzipped data omitted>
        """
        return send_from_directory(current_app.config['DATA_DIR'],
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
