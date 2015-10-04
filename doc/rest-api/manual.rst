.. _api-manual:

REST API manual
===============

This page documents the REST server API exposed by Varda to client
applications.

For more detailed information on specific API endpoints, see
:ref:`api-resources`.


.. _api-example:

An example request using `curl`
-------------------------------

To get us started, here's an example of creating a new :ref:`sample
<api-resources-samples>` resource named `1000 Genomes` using `curl`:

.. sourcecode:: bash

    curl -u user:password -X POST -H 'Content-Type: application/json' \
      -d '{"name": "1000 Genomes"}' https://example.com/samples/

The first thing to observe is that the request is authenticated using HTTP
Basic Authentication (the ``-u user:password`` argument). See
:ref:`api-authentication` for more information.

The request body is a JSON document (specified with the `Content-Type` header)
consisting of only a `name` field with value ``1000 Genomes``. See
:ref:`api-data` for more ways of sending data.

Finally, the request is done at the collection endpoint for :ref:`sample
<api-resources-samples>` resources using the `POST` method. This is the
typical way of creating new resources and you can find more information on
specific resources in :ref:`api-resources`.

What we'll get back is the following HTTP response:

.. sourcecode:: http

    HTTP/1.1 201 CREATED
    Server: gunicorn/18.0
    Date: Sat, 16 Nov 2013 10:03:17 GMT
    Connection: close
    Content-Type: application/json
    Content-Length: 282
    Location: https://example.com/samples/140
    Api-Version: 0.3.0

    {
      "sample": {
        "uri": "/samples/140",
        "active": false,
        "added": "2013-11-16T10:47:28.711076",
        "coverage_profile": true,
        "name": "1000 Genomes",
        "notes": null,
        "pool_size": 1,
        "public": false,
        "user": {
          "uri": "/users/1"
        }
      }
    }

The response body contains a representation of the created resource as a JSON
document. We can follow the `Location` header to that same resource.

.. note:: For brevity, we'll omit many of the headers in example HTTP requests
   and responses from now on.


.. _api-authentication:

Authentication
--------------

Many requests require user authentication which can be provided with HTTP
Basic Authentication or token authentication.

Authentication state can be checked on the :ref:`authentication
<api-resources-authentication>` resource.


.. _api-authentication-basic:

HTTP Basic Authentication
^^^^^^^^^^^^^^^^^^^^^^^^^

For interactive use of the API, the most obvious way of authenticating is by
providing a username and password with HTTP Basic Authentication.

.. seealso:: `Wikipedia article on HTTP Basic Authentication
   <http://en.wikipedia.org/wiki/Basic_access_authentication>`_


.. _api-authentication-token:

Token authentication
^^^^^^^^^^^^^^^^^^^^

Automated communication with the API is better authenticated with a
`token`. An authentication token is a secret string uniquely identifying a
user that can be used in the `Authorization` request header. The value of this
header should then be the string ``Token``, followed by a space, followed
by the token string. For example:

.. sourcecode:: http

    GET /samples HTTP/1.1
    Authorization: Token 5431792000be7601697fb5a4005984ebdd60320c

Authentication tokens are themselves resources and can be managed using the
API, see :ref:`api-resources-tokens`.


.. _api-data:

Passing data with a request
---------------------------

Data can be attached to a request in three ways:

1. As query string parameters.
2. As HTTP form data.
3. In a JSON-encoded request body.

Generally, using a JSON-encoded request body is preferred since it offers
richer structure. For example, JSON has separate datatypes for strings and
numbers, and supports nesting for more complex documents.

.. note:: A JSON-encoded request body is also accepted with GET requests, even
   though this is perhaps not true to the HTTP specification.

JSON-encoded bodies must always be accompanied with a ``application/json``
value for the `Content-Type` header.


String encoding of lists and objects
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There is limited support for sending structured data as query string
parameters or HTTP form data by serializing them. Lists are serialized by
concatenating their items with `,` (comma) in between. Objects of name/value
pairs are serialized similarly where the items are concatenations of name, `:`
(colon) and value.

For example, the JSON list ::

    [45, 3, 11, 89]

is serialized as::

    45,3,11,89

Similarly, the JSON object ::

    {
      "name1": "value1",
      "name2": "value2",
      "name3": "value3"
    }

is serialized as::

    name1:value1,name2:value2,name3:value3

.. note:: The decoding of these serializations is very primitive. For example,
   escaping of `,` (comma) or `:` (colon) is not possible.


.. _api-datetime:

Date and time
-------------

All date and time values are formatted as strings following ISO 8601.

.. seealso:: `Wikipedia article on ISO 8601
   <http://en.wikipedia.org/wiki/ISO_8601>`_


.. _api-queries:

Queries
-------

A *query* defines a set of samples, used to calculate observation frequencies
over when annotationg variants. A query is represented as an object with two
fields:

**name** (`string`)
  Name for this query (alphanumeric).

**expression** (`string`)
  Search query string.

The `expression` field is a boolean search query string in which clauses can
reference :ref:`sample <api-resources-samples>` resources and :ref:`group
<api-resources-groups>` resources. This is the grammar for query expressions::

    <expression> ::= <tautology>
                   | <clause>
                   | "(" <expression> ")"
                   | "not" <expression>
                   | <expression> "and" <expression>
                   | <expression> "or" <expression>

    <tautology> ::= "*"

    <clause> ::= <resource-type> ":" <uri>

    <resource-type> ::= "sample" | "group"

The tautology query ``*`` matches all samples. A clause of the form
``sample:<uri>`` matches the sample with the given URI. A clause of the form
``group:<uri>`` matches samples that are in the group with the given URI.

When creating the set of samples matched by a query expression, only active
samples with a coverage profile are considered. The exception to this are
expressions of the form ``sample:<uri>``, which can match inactive samples or
samples without coverage profile.

As an example, the following is an expression matching the sample with URI
``/samples/5`` and samples that are in the group with URI ``/groups/3`` but
not in the group with URI ``/groups/17``::

    sample:/samples/5 or (group:/groups/3 and not group:/groups/17)


.. _api-links:

Linked resources and embeddings
-------------------------------

Resources can have links to other resources. In the resource representation,
such a link is an object with a `uri` field containing the linked resource
URI.

For some links, the complete representation of the linked resource can be
embedded instead of just the `uri` field. This is documented with the resource
representation.

For example, :ref:`sample <api-resources-samples>` resources can have the
linked :ref:`user <api-resources-users>` resource embedded:

.. sourcecode:: http

    GET /samples/130?embed=user

.. sourcecode:: http

    HTTP/1.1 200 OK
    Content-Type: application/json

    {
      "sample": {
        "uri": "/samples/130",
        "active": false,
        "added": "2013-03-30T00:18:48.298526",
        "coverage_profile": false,
        "name": "1KG phase1 integrated call set",
        "notes": null,
        "pool_size": 1092,
        "public": true,
        "user": {
          "uri": "/users/2",
          "added": "2012-11-30T20:28:11.409536",
          "email": null,
          "login": "martijn",
          "name": "Martijn Vermaat",
          "roles": [
            "trader",
            "annotator"
          ]
        }
      }
    }


.. _api-collection-resources:

Collection resources
--------------------

A collection resource is a grouping of any number of instance resources. Use a
`POST` request on the collection resource to add an instance resource to
it. Listing the instance resources is done with a `GET` request and comes with
a number of utilities as described below.


Representation
^^^^^^^^^^^^^^

A collection resource is represented as an object with two fields:

**uri** (`uri`)
  URI for this collection resource.

**items** (`list` of `object`)
  List of resource instances.


Range requests / pagination
^^^^^^^^^^^^^^^^^^^^^^^^^^^

A `GET` request on a collection resource **must** have a `Range` header
specifying the range of instance resources (using `items` as range unit) that
is requested. The response will contain the appropriate `Content-Range` header
showing the actual range of instance resources that is returned together with
the total number available.


Filtering
^^^^^^^^^

The returned list of recourse instances can sometimes be filtered by
specifying values for resource fields. Documentation for the resource
collection lists the fields that can be used to filter on.

For example, the :ref:`sample collection <api-resources-samples-collection>`
resource can be filtered on the `public` and `user` fields.


Ordering
^^^^^^^^

The ordering of the returned list of resource instances can be specified in
the `order` field as a list of field names. Field names can be prefixed with a
`-` (minus) for descending order or with a `+` (plus) for ascending order
(default) and must be chosen from the documented set of orderable fields for
the relevant collection resource.

For example, the :ref:`sample collection <api-resources-samples-collection>`
resource can be ordered by the `name`, `pool_size`, `public`, `active`, and
`added` fields.

All resource collections have a default order of their items which is usually
ascending by URI (the :ref:`variant collection
<api-resources-samples-collection>` being the exception).


Example `GET` request
^^^^^^^^^^^^^^^^^^^^^

We illustrate some of the described utilities by listing public samples
ordered first descending by `pool_size` and second ascending by `name`. We
request only the first 6 of them.

Example request:

.. sourcecode:: http

    GET /samples/?public=true&order=-pool_size,name HTTP/1.1
    Range: items=0-5

Example response:

.. sourcecode:: http

    HTTP/1.1 206 PARTIAL CONTENT
    Content-Type: application/json
    Content-Range: items 0-5/8

    {
      "sample_collection": {
        "uri": "/samples/",
        "items": [
          {
            "uri": "/samples/130",
            "name": "1KG phase1 integrated call set",
            "pool_size": 1092,
            "public": true,
            ...
          },
          {
            "uri": "/samples/134",
            "name": "My sample",
            "pool_size": 4,
            "public": true,
            ...
          },
          {
            "uri": "/samples/135",
            "name": "A new sample",
            "pool_size": 3,
            "public": true,
            ...
          },
          {
            "uri": "/samples/129",
            "name": "Another sample",
            "pool_size": 1,
            "public": true,
            ...
          },
          {
            "uri": "/samples/131",
            "name": "Sample 42",
            "pool_size": 1,
            "public": true,
            ...
          },
          {
            "uri": "/samples/128",
            "name": "Some test sample",
            "pool_size": 1,
            "public": true,
            ...
          }
        ]
      }
    }


.. _api-tasked-resources:

Tasked resources
----------------

A tasked resource is a type of resource associated with a server task. This
task is scheduled upon creation of a new resource instance (i.e., via a `POST`
request on the corresponding collection resource).

Information on the server task can be obtained with a `GET` request on the
instance resource. A task can be re-scheduled by setting the `state` field to
the empty object in a `PATCH` request (this requires the `admin` role).


Representation
^^^^^^^^^^^^^^

A tasked resource representation has a field `task` containing an object with
the following fields:

**state** (`string`)
  Task state. Possible values for this field are `waiting`, `running`,
  `succes`, and `failure`.

**progress** (`integer`)
  Task progress as an integer in the range 0 to 100. Only present if the
  `state` field is set to `running`.

**error** (`object`)
  An :ref:`error object <api-errors>`. Only present if the `state` field is
  set to `failure`.


.. _api-versioning:

Versioning
----------

The API is versioned following `Semantic Versioning
<http://semver.org/>`_. Clients can (but are not required to) ask for specific
versions of the API with a Semantic Versioning specification in the
`Accept-Version` header.

If the server can match the specification, or `Accept-Version` is not set, the
response will include the API version in the `Api-Version` header. If the
specification cannot be matched, a 406 status is returned with a
`no_acceptable_version` error code.

Example request with `Accept-Version` header, and corresponding response:

.. sourcecode:: http

    GET /
    Accept-Version: >=0.3.1,<1.0.0

.. sourcecode:: http

    HTTP/1.1 200 OK
    Api-Version: 0.4.2

.. note:: Currently the server implements one specific API version so there is
   no real negotiation on version. More sophisticated logic based on
   `Accept-Version` may be implemented in the future.


.. _api-errors:

Error responses
---------------

If a request results in the occurrence of an error, the server responds by
sending an appropriate HTTP status code and an error document containing:

1. An :ref:`error code <api-error-codes>` (`code`).
2. A human readable error message (`message`).

These fields are wrapped in an object called `error`.


Example request resulting in error
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following request aims to create a new :ref:`sample
<api-resources-samples>` resource with name `Test sample` and pool size
`Thirty`:

.. sourcecode:: http

    POST /samples/ HTTP/1.1
    Content-Type: application/json

    {
      "name": "Test sample",
      "pool_size": "Thirty"
    }

Of course, pool size should be encoded as an integer and therefore the
following response is returned:

.. sourcecode:: http

    HTTP/1.1 400 Bad Request
    Content-Type: application/json

    {
      "error":
        {
          "code": "bad_request",
          "message": "Invalid request content: value of field 'pool_size' must be of integer type"
        }
    }


.. _api-error-codes:

List of error codes
^^^^^^^^^^^^^^^^^^^

Here's an incomplete list of error codes with their meaning.

`bad_request`
  Invalid request content (`message` field contains more details).

`basic_auth_required`
  The request requires login/password authentication.

`entity_too_large`
  The request entity is too large.

`forbidden`
  Not allowed to make this request.

`integrity_conflict`
  The request could not be completed due to a conflict with the current state
  of the resource (`message` field contains more details).

`internal_server_error`
  The server encountered an unexpected condition which prevented it from
  fulfilling the request.

`no_acceptable_version`
  The requested version specification did not match an available API version.

`not_found`
  The requested entity could not be found.

`not_implemented`
  The functionality required to fulfill the request is currently not
  implemented.

`unauthorized`
  The request requires user authentication.

`unsatisfiable_range`
  Requested range not satisfiable.


.. _api-status-codes:

Summary of HTTP status codes
----------------------------

We give a brief overview of response status codes sent by the server and their
meaning. For more information, consult `HTTP/1.1: Status Code Definitions`_.

200
  Everything ok, the request has succeeded.

201
  The request has been fulfilled and resulted in a new resource being created.

206
  The server has fulfilled the partial GET request for the resource.

301
  Moved permanently.

400
  The request data was malformed.

401
  The request requires user authentication.

403
  Not allowed to make this request.

404
  Nothing was found matching the request URI.

406
  The resource identified by the request is only capable of generating
  response entities which have content characteristics not acceptable
  according to the accept headers sent in the request.

409
  The request could not be completed due to a conflict with the current state
  of the resource.

413
  The request entity was too large.

416
  Requested range not satisfiable.

500
  Internal server error.

501
  Not implemented.


.. _HTTP/1.1\: Status Code Definitions: http://www.w3.org/Protocols/rfc2616/rfc2616-sec10.html
