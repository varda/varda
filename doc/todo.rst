Todo list
=========

* Import data source directly from URL without uploading.
* Everything must be in UTF8.
* Use Alembic for database migrations.
* Generated REST API documentation, also using Sphinx?
* Other types of authentication (OAuth).
* Document server deployment and local installation separately.
* Add setup.py with ``entry_points={'console_scripts': ['varda-manage = varda.manage:main']}``.


Check reference allele with reference
-------------------------------------

Some simple tests showed dat it doesn't add much overhead to the import task
if we also check if the reference allele from the VCF matches the reference
sequence (e.g. hg19.fasta). Test done using the pyfasta library.

Having access to a reference fasta file would open some new possibilities:

* Validate VCF chromosome name.
* Validate VCF positions (don't exceed chromosome length).
* Validate VCF reference allele.
* Normalize the variant even further than we do now (using
  ``vcf.utils.trim_common_suffix``), rolling the variant upstream/downstream
  as far as possible.

However, I think some of this should be configurable. Also, what to do when a
VCF record does not validate. Reject the file entirely? Silently skip the
record? Reject if > 95% doesn't validate?


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


Frequency calculations
----------------------

Sex should be taken into account when calculating frequencies on sex
chromosomes. For example, in a pool of 500 (250 females, 250 males), the
maximum frequency on the Y chromosome is 250. This is not a problem for
samples where we have coverage tracks, since we use them to calculate
frequencies (e.g. female samples won't have coverage on Y).

For population studies, where we don't have coverage tracks, we should
have the option to manually set the number of male/female samples, and take
that into account in calculations. If this ratio is unknown, things will be
harder (we might be able to deduce something from variants on X and Y). In
any case, communicate clearly what the calculation exactly is.

To be more flexible in reference genome, number of copies per chromosome in
male and female should be specified in the server configuration.

We might also just ignore this issue, since population study frequencies will
probably only reported separately per study and in that case it's quite easy
for the user to take the number of males/females into account.
