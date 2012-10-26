Varda server
============

A database for genomic variation.

.. warning:: This is a work in progress, probably not yet ready for use!

Varda is an application for storing genomic variation data obtained from
next-generation sequencing experiments, such as full-genome or exome
sequencing of individuals or populations. Variants can be imported from
standard formats such as `VCF files <http://www.1000genomes.org/wiki/Analysis/Variant%20Call%20Format/vcf-variant-call-format-version-41>`_,
and annotated for presence in previously imported datasets.

Varda is implemented by very loosely coupled components, communicating using
a RESTful protocol over HTTP with json-encoded response payloads.

* *Varda server:* Exposes a RESTful API for managing and querying the
  variant database.
* *Varda client:* Command line client for querying the server
  non-interactively.
* *Varda web:* Web interface for browsing the server interactively.

This is Varda server.


Contents
--------

Documentation for users of Varda server:

.. toctree::
   :maxdepth: 1

   intro
   copyright
   install
   rest-api

For developers working on Varda server:

.. toctree::
   :maxdepth: 1

   design
   api
   todo
   links


Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
