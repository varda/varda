Introduction
============

Varda is an application for storing genomic variation data obtained from
next-generation sequencing experiments, such as full-genome or exome
sequencing of individuals or populations. Variants can be imported from
standard formats such as `VCF files <http://www.1000genomes.org/wiki/Analysis/Variant%20Call%20Format/vcf-variant-call-format-version-41>`_,
and annotated with their frequencies in previously imported datasets.

Varda is implemented by very loosely coupled components, communicating using
a RESTful protocol over HTTP with JSON-encoded response payloads.

* **Varda** - Server exposing a RESTful API for managing and querying the
  variant database.
* **Manwë** - Python client library and command line interface to Varda.
* **Aulë** - Web interface to Varda.

This is Varda.


Varda
-----

The server is implemented in Python using the `Flask <http://flask.pocoo.org/>`_
framework and directly interfaces the `PostgreSQL <http://www.postgresql.org>`_
(or `MySQL <http://www.mysql.com>`_) database backend using `SQLAlchemy <http://www.sqlalchemy.org/>`_.
It exposes a `RESTful <http://en.wikipedia.org/wiki/Representational_state_transfer>`_
API over HTTP where response payloads are (currently only) JSON-encoded. A
future version may use other encodings, depending on the value of the
``Accept-Encoding`` header sent by the client.

Long-running actions are executed asynchonously through the `Celery <http://celeryproject.org/>`_
distributed task queue.

Varda is licensed under the :doc:`MIT License </copyright>`.
