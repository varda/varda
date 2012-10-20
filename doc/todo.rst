Todo list
=========

* Import data source directly from URL without uploading.
* Everything must be in UTF8.
* Use Alembic for database migrations.
* Generated REST API documentation, also using Sphinx?
* Other types of authentication (OAuth).
* Documentation of installation/usage scenarios for main use cases.
* Document server deployment and local installation separately.


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
