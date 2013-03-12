Todo list
=========

* Everything must be in UTF8.
* Other types of authentication (OAuth).
* Better docs.
* Add setup.py with ``entry_points={'console_scripts': ['varda-manage = varda.manage:main']}``.
* Validate user input, especially file uploads (max file size).
* Less granular API, e.g. way to import and annotate sample with fewer requests.
* Use accept HTTP headers in the API.
* More comprehensive test suite.
* Optionally only import variants from VCF file with PASS.
* Throtling.
* Better rights/roles model.
* For samtools VCF's, don't rely on GT, but decide from PL.
* Support input in BCF2 format.
* Have a look at supporting the `gVCF format <https://sites.google.com/site/gvcftools/)>`_.
* Attach tags (e.g. 'exome', 'illumina', 'cancer').


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
