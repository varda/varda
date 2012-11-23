REST server API
===============

.. Todo: Modify sphinxcontrib-httpdomain with an :autoroute: directive, such
   that we can manually include documentation for specific resources (and in
   the order we define, which is random with the :autoflask: directive).

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

If a request requires user authentication, it should be performed using
`HTTP Basic Authentication <http://en.wikipedia.org/wiki/Basic_access_authentication>`_.


.. _api_users:

Users
-----

.. autodocstring:: varda.api.serialize.serialize_user


.. _api_samples:

Samples
-------

.. autodocstring:: varda.api.serialize.serialize_sample


.. _api_variations:

Sets of observations
--------------------

.. autodocstring:: varda.api.serialize.serialize_variation


.. _api_coverages:

Sets of regions
---------------

.. autodocstring:: varda.api.serialize.serialize_coverage


.. _api_annotations:

Annotations
-----------

.. autodocstring:: varda.api.serialize.serialize_annotation


.. _api_data_sources:

Data sources
------------

.. autodocstring:: varda.api.serialize.serialize_data_source


.. _api_exceptions:

Errors
------

.. autodocstring:: varda.api.serialize.serialize_exception



Requests
--------

The following are all HTTP requests that can be made on the API.

.. autoflask:: varda:create_app()
   :undoc-static:
