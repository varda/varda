.. _intro:

Introduction
============

Varda is an application for storing genomic variation data obtained from
next-generation sequencing experiments, such as full-genome or exome
sequencing of individuals or populations. Variants can be imported from
standard formats such as `VCF`_ files and annotated with their frequencies in
previously imported datasets.

Varda is implemented as a service exposing a RESTful HTTP interface. Two
clients for this interface are under development:

* `Manwë`_ - Python client library and command line interface to Varda.
* `Aulë`_ - Web interface to Varda.


Use cases
---------

The following are some example use cases which Varda is designed to support.

* *Private exome variant database for a sequencing lab*

  Installed on the local network, Varda can be used to import and annotate
  variants from all exome sequencing experiments at a sequencing
  lab. Additionally, the database could contain public datasets from
  population studies (e.g., 1000 Genomes, Genome of the Netherlands), such
  that all exome experiments are also annotated with frequencies in those
  studies.

.. _intro-use-case-groups:

* *Shared database between several groups*

  Several sequencing centers can import their variants in a central Varda
  installation which can subsequently be used by the same centers for
  frequency annotation. The system can be setup such that annotation is only
  possible on previously imported data (to encourage sharing).

  Data from one center can only be accessed anonymized by other groups, since
  only the frequencies over the entire databased are available. To accomodate
  even stricter anonymity, samples can be imported after pooling.

* *Publicly sharing variant frequencies from a population study*

  Variation data from a population study can be imported in a Varda
  installation accessible over the internet such that others can annotate
  their data with frequencies in the study.

For contrast, consider the following examples of what Varda is *not* designed
to do.

* *Sharing and browsing genomic variants*

  Varda is focussed on sharing variant frequencies only, and as such is not
  designed for direct browsing. Other systems, such as `LOVD`_, are much more
  suitable for sharing and browsing genomic variants and additionally store
  phenotypes and other metadata.

* *Ad-hoc exploration of genomic variation*

  Again, Varda is focussed on sharing variant frequencies only, and does not
  store additional metadata nor does it allow for effective exploration of
  variants. If you have variation data from a disease or population study
  which you want to analyse in a flexible way, have a look at `gemini`_.


Implementation
--------------

The server is implemented in Python using the `Flask`_ framework and directly
interfaces the `PostgreSQL`_ (or `MySQL`_) database backend using
`SQLAlchemy`_. It exposes a `RESTful <REST>`_ API over HTTP where response
payloads are JSON-encoded.

Long-running actions are executed asynchonously through the `Celery`_
distributed task queue.


.. _Aulë: https://github.com/varda/aule
.. _Celery: http://celeryproject.org/
.. _FlasK: http://flask.pocoo.org/
.. _gemini: https://github.com/arq5x/gemini
.. _LOVD: http://lovd.nl/
.. _Manwë: https://github.com/varda/manwe
.. _MySQL: http://www.mysql.com/
.. _PostgreSQL: http://www.postgresql.org
.. _REST: http://en.wikipedia.org/wiki/Representational_state_transfer
.. _SQLAlchemy: http://www.sqlalchemy.org/
.. _VCF: http://www.1000genomes.org/wiki/Analysis/Variant%20Call%20Format/vcf-variant-call-format-version-41
