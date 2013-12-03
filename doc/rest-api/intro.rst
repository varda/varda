Introduction to the REST API
============================

For communication with client applications, Varda exposes an API
:ref:`following the REST architectural style <rest-conformance>`. The API
represents resources in `JSON <http://www.json.org>`_ format and user
authentication is done using
`HTTP Basic Authentication
<http://en.wikipedia.org/wiki/Basic_access_authentication>`_.

Start by going through the :ref:`API manual <api-manual>`. After that, read
through the documentation for the individual :ref:`resources
<api-resources>`.


.. _rest-conformance:

Conformance with REST
---------------------

Although Varda tries to follow `REST
<https://en.wikipedia.org/wiki/Representational_state_transfer>`_ in its API,
there are certainly parts of the API that are not completely in the spirit of
REST.

Todo: More text here, at least covering the following points:

- JSON is not a hypertext format
- Accepting a request body with GET
- Todo
