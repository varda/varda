Varda
=====

A database for genomic variation frequencies.

.. warning:: This is a work in progress, probably not yet ready for use!

Varda is an application for storing genomic variation data obtained from
next-generation sequencing experiments, such as full-genome or exome
sequencing of individuals or populations. Variants can be imported from
standard formats such as `VCF`_ files and annotated with their frequencies in
previously imported datasets.

Varda is implemented as a service exposing a RESTful HTTP interface. Two
clients for this interface are under development:

* `Manwë`_ - Python client library and command line interface to Varda.
* `Aulë`_ - Web interface to Varda.


Documentation for users
-----------------------

This section of the documentation aims to guide users through working with
Varda. Users range from API client developers to end users working with Varda
through a web client.

.. toctree::
   :maxdepth: 2

   intro
   guide
   rest-api/index


Documentation for administrators
--------------------------------

Start here if you're responsible for getting Varda running on a system.

.. toctree::
   :maxdepth: 2

   install
   config
   run


Documentation for developers
----------------------------

This part is for developers working on Varda. It needs work, sorry about
that.

.. toctree::
   :maxdepth: 1

   design
   todo
   links
   api/index


Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


.. _Aulë: https://github.com/martijnvermaat/aule
.. _Manwë: https://github.com/martijnvermaat/manwe
.. _VCF: http://www.1000genomes.org/wiki/Analysis/Variant%20Call%20Format/vcf-variant-call-format-version-41
