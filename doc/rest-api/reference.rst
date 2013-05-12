REST API reference
==================

.. todo:: Rewrite this entire section.

.. todo:: Include info that's in the (obsolete) individual files per resource.


Annotations
-----------

Todo.


Coverages
---------

Todo.


Data sources
------------

Todo.


Samples
-------

Todo.


Users
-----

Todo.


Variants
--------

Todo.


Variations
----------

Todo.


.. _api_misc:

Special endpoints
-----------------

.. autoflask:: varda:create_app()
   :endpoints: api.root_get, api.authentication_get


.. _api_exceptions:

Errors
------

Errors are represented as objects with the following fields:

* **code** (`string`) - Error code (todo: document error codes).
* **message** (`string`) - Human readable error message.

If an error occurs, the server responds with an error object as `error` and an
appropriate status code.

Example request:

.. sourcecode:: http

    PATCH /samples/3 HTTP/1.1
    Content-Type: application/json

    {
      "active": true
    }

Example response:

.. sourcecode:: http

    HTTP/1.1 400 Bad Request
    Content-Type: application/json

    {
      "error":
        {
          "code": "activation_failure",
          "message": "Sample could not be activated for some reason"
        }
    }
