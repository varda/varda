REST server API
===============

.. Todo: Cleanup this intro.

This page documents the REST server API exposed by Varda server to client
applications.

In general, the following HTTP error status codes can be returned on any
request:

* **400** - The request data was malformed.
* **401** - The request requires user authentication.
* **403** - Not allowed to make this request.
* **404** - Nothing was found matching the request URI.
* **413** - The request entity was too large.
* **501** - Not implemented.

All of them come with an :ref:`error <api_exceptions>` object as `error` in
the response. Other status codes are documented with each request below.

All date and time values are formatted following
`ISO 8601 <http://en.wikipedia.org/wiki/ISO_8601>`_.

In the HTTP request/response examples below, some of the HTTP headers are
omitted for brevity.

Request content must be in `JSON <http://www.json.org>`_ format. An exception
is request content with no nested data and only string datatypes, this can
also be HTTP form data. Example of an API request using `curl`:

.. sourcecode:: bash

    curl -u user:password -X POST -H 'Content-Type: application/json' \
        -d '{"name": "1000 Genomes"}' https://example.com/samples

Response content is always in JSON format.

If a request requires user authentication, it should be performed using
`HTTP Basic Authentication <http://en.wikipedia.org/wiki/Basic_access_authentication>`_.
Authentication state can be checked on the :http:get:`authentication endpoint </authentication>`.


.. _api_users:

Users
-----

.. autodocstring:: varda.api.serialize.serialize_user

.. autoflask:: varda:create_app()
   :endpoints: api.users_list, api.users_get, api.users_add


.. _api_samples:

Samples
-------

.. autodocstring:: varda.api.serialize.serialize_sample

.. autoflask:: varda:create_app()
   :endpoints: api.samples_list, api.samples_get, api.samples_add, api.samples_update


.. _api_variations:

Sets of observations
--------------------

.. autodocstring:: varda.api.serialize.serialize_variation

.. autoflask:: varda:create_app()
   :endpoints: api.variations_list, api.variations_get, api.variations_import_status, api.samples_add


.. _api_coverages:

Sets of regions
---------------

.. autodocstring:: varda.api.serialize.serialize_coverage

.. autoflask:: varda:create_app()
   :endpoints: api.coverages_list, api.coverages_get, api.coverages_import_status, api.coverages_add


.. _api_data_sources:

Data sources
------------

.. autodocstring:: varda.api.serialize.serialize_data_source

.. autoflask:: varda:create_app()
   :endpoints: api.data_sources_list, api.data_sources_get, api.data_sources_data, api.data_sources_add

.. Todo: Note that the data_sources_data response content is not JSON.


.. _api_annotations:

Annotations
-----------

.. autodocstring:: varda.api.serialize.serialize_annotation

.. autoflask:: varda:create_app()
   :endpoints: api.annotations_list, api.annotations_get, api.annotations_write_status, api.annotations_add


.. _api_exceptions:

Errors
------

.. autodocstring:: varda.api.serialize.serialize_exception


Miscellaneous
-------------

.. autoflask:: varda:create_app()
   :endpoints: api.apiroot, api.authentication
