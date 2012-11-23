REST server API
===============

This page documents the REST server API exposed by Varda server to client
applications.

In general, the following HTTP status codes can be returned on any request:

* **404** - Nothing was found matching the request URI. Respond with an
    :ref:`error <api_exceptions>` object as `error`.
* **401** - The request requires user authentication. Respond with an
    :ref:`error <api_exceptions>` object as `error`.

Other status codes are documented with each request.

All date and time values are formatted following `ISO 8601 <http://en.wikipedia.org/wiki/ISO_8601>`_.

In the HTTP request/response examples below, some of the HTTP headers are
omitted for brevity.


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
