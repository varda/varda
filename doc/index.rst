Varda
=====

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


User documentation
------------------

This section of the documentation aims to guide users through working with
Varda.

.. toctree::
   :maxdepth: 2

   intro
   guide


Managing Varda
--------------

Start here if you're responsible for getting Varda running on a system.

.. toctree::
   :maxdepth: 2

   install
   upgrade
   config
   run


REST API documentation
----------------------

Developers of client applications can read how to communicate with the Varda
REST API in this section.

.. toctree::
   :maxdepth: 2

   rest-api/overview
   rest-api/reference


Additional notes
----------------

This part contains some notes for developers and other random notes. It needs
work, sorry about that.

.. toctree::
   :maxdepth: 2

   design
   todo
   changelog
   copyright
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
