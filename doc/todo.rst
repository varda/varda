Todo list
=========

* Other types of authentication (OAuth).
* Better docs.
* More strict validation of user input, especially file uploads (max file size
  and contents).
* Use accept HTTP headers in the API.
* More comprehensive test suite.
* Throtling.
* Better rights/roles model.
* Support input in BCF2 format.
* Have a look at supporting the `gVCF format <https://sites.google.com/site/gvcftools/)>`_.
* Attach tags (e.g. 'exome', 'illumina', 'cancer').
* Possibility to contact submitter of an observation.


Queries
-------

Idea to better implement querying variant frequencies. Have a new `queries`
resource collection, where we can create a new `query` resource with the
following fields:

- `description`: Textual description of the query (used in VCF header).
- `slug`: Short identifier consisting of only letters (used as VCF field).
- `exclude_samples`: List of samples to exclude.
- `within_sample`: Sample to restrict calculation to, or None for a global
    calculation.

In the future, we could extend this. For example, if we can attach tags to
samples, queries could include or exclude samples with a certain tag.

Now, each annotation references one or more queries. Ad-hoc frequency
calculations on a single variant or region, could be modelled as sub
resources of the query (so multiple queries on one variant must be done
separately).

By the way, I'm not convinced we need the option to exclude samples from
the calculation. The main problem it solves is making sure we don't include
the observations we are currently annotating if they are already in the
database. This can simply be solved by excluding the current data source
from the calculation. Or, generalizing, excluding any data source with the
same checksum.


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
