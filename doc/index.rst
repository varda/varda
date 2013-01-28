Varda
=====

A database for genomic variation frequencies.

.. warning:: This is a work in progress, probably not yet ready for use!

Varda is an application for storing genomic variation data obtained from
next-generation sequencing experiments, such as full-genome or exome
sequencing of individuals or populations. Variants can be imported from
standard formats such as `VCF files <http://www.1000genomes.org/wiki/Analysis/Variant%20Call%20Format/vcf-variant-call-format-version-41>`_,
and annotated with their frequencies in previously imported datasets.

Varda is implemented by very loosely coupled components, communicating using
a RESTful protocol over HTTP with json-encoded response payloads.

* **Varda** - Server exposing a RESTful API for managing and querying the
  variant database.
* **Manwë** - Python client library and command line interface to Varda.
* **Aulë** - Web interface to Varda.

This is Varda.


Contents
--------

Documentation for users of Varda:

.. toctree::
   :maxdepth: 1

   intro
   copyright
   install
   rest-api/index

For developers working on Varda:

.. toctree::
   :maxdepth: 1

   design
   api/index
   todo
   links


Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
