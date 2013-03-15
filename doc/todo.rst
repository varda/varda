Todo list
=========

* Other types of authentication (OAuth).
* Better docs.
* Validate user input, especially file uploads (max file size) and max length
  for string parameters.
* Use accept HTTP headers in the API.
* More comprehensive test suite.
* Throtling.
* Better rights/roles model.
* Support input in BCF2 format.
* Have a look at supporting the `gVCF format <https://sites.google.com/site/gvcftools/)>`_.
* Attach tags (e.g. 'exome', 'illumina', 'cancer').
* Possibility to contact submitter of an observation.


Document use cases
------------------

Some use cases to be documented:

* *Scenario: private database for a sequencing lab*

  Import and annotate variants from all sequencing experiments at an
  institution. The database should also contain public datasets from
  population studies (e.g. 1KG, GoNL).

  Authentication and authorization scheme is probably simple.

* *Scenario: shared database between several groups*

  All groups import variants from their own sequencing experiments and
  annotation is only possible for previously imported data. Data can only be
  used anonymized by other groups (just overall frequencies in the database)
  and to accomodate even stricter anonymity, samples can be imported after
  pooling.

  Authentication and authorization scheme is more complex.

* *Import public dataset: 1000 Genomes*

* *Import public dataset: Genome of the Netherlands*
