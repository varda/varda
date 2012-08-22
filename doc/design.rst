Application design
==================

.. note:: Work in progress, some of this should probably be refactored into
    user documentation.


Sample types
------------

Three types of samples:

1. Simple sample (one individual)
2. Pooled sample (multiple individuals)
3. Population study

The following table gives a summary of what is stored for each sample type:

=========================== ================ ==================== ================
Stored data                 Simple sample    Pooled sample        Population study
=========================== ================ ==================== ================
Pool size                   1                N                    N
Variant observations        O with support 1 N x O with support 1 O with support N
Observation coverage        Yes              Yes                  No
Covered regions             R                N x R                None
=========================== ================ ==================== ================

- N = number of individuals
- O = number of observations per individual
- R = number of covered regions per individual

For all sample types, data can be imported from an arbitrary number of data
sources. This means you could for example import variant observations per
individual, per chromosome, or per variant type.

Pooled samples can have their individuals effectively anonymized by importing
variant observations from one big data source in which the order is not
related to the individuals. For example, ``cat`` the VCF files for all
individuals and sort the result by genome position before sending it to the
server.

.. note:: Observation coverage (total number of reads and number of variant
    reads, both per individual) is only stored for observations in exactly one
    individual (i.e. not in population studies).


Frequency calculation
---------------------

Only take samples into account with covered regions (to rule out population
studies).


Sample state
------------

A sample can be either *active* or *inactive* (default). An inactive sample is
ignored in any frequency calculations.

Importing data sources is only possible for inactive samples. A sample cannot
be made active while any data source is being imported for that sample. Users
can only make a sample active, not inactive.


Trading observations
--------------------

One use case of Varda server is sharing variant observations between different
parties where it undesirable that a certain party only uses the data for
annotation without sharing its variant observations.

In such a setup, the *trader* role can be used. This role permits annotating a
data source, given it has been imported (and the sample it belongs to is
active).

Of course this mechanical barrier can be cheated in various ways, but it at
least makes sure no party forgets to import its samples.
