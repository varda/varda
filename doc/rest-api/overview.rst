Overview of the REST API
========================

.. todo:: Rewrite this entire section.

This page documents the REST server API exposed by Varda to client
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
