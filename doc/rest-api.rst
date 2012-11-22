REST server API
===============

This page documents the REST server API exposed by Varda server to client
applications.

In general, the following HTTP status codes can be returned on any request:

* **200** - The request has succeeded.
* **404** - Nothing was found matching the request URI.

Other status codes specific to a request are documented with that request.


.. _users:

Users
-----

(Todo: Perhaps this should be in the serializer docstring. Can we include it
here from there?)

A user resource is represented as an object with the following fields:

* **uri** (`string`) - URI for this user.
* **name** (`string`) - Name of this user.
* **login** (`string`) - Login name.
* **roles** (`list` of `string`) - Roles this user has.
* **added** (`string`) - Date this user was added in ISO todo.

Example representation:

.. sourcecode:: json

    {
      "uri": "/users/34",
      "name": "Frederick Sanger",
      "login": "fred",
      "roles": ["admin"],
      "added": "2012-10-23"
    }


.. _data_sources:

Data sources
------------

A data source resource is represented as an object with the following fields:

* **uri** (`string`) - URI for this data source.
* **user** (`string`) - URI for the data source owner.
* **annotations** (`string`) - URI for the data source annotations.
* **data** (`string`) - URI for the data.
* **name** (`string`) - Name of this data source.
* **filetype** (`string`) - Data filetype.
* **gzipped** (`bool`) - Whether data is compressed.
* **added** (`string`) - Date this data source was added in ISO todo.

Example representation:

.. sourcecode:: json

    {
      "uri": "/data_sources/23",
      "todo": "..."
    }


Requests
--------

The following are all HTTP requests that can be made on the API.

.. autoflask:: varda:create_app()
   :undoc-static:
   :include-empty-docstring:
