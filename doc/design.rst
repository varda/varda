Application design
==================

.. note:: Work in progress, some of this should probably be refactored into
    user documentation.


Implementation
--------------

Varda is implemented on top of the `Flask web microframework <http://flask.pocoo.org/>`_,
the `Celery distributed task queue <http://celeryproject.org/>`_, and the
`SQLAlchemy object relational mapper <http://www.sqlalchemy.org/>`_.

A typical deployment looks like this::

                                ________
                               /        \
                              |\________/|
                 ___________  |          |  ___________
               /              | Database |              \
              |               |          |               |
              |                \________/                |
              |                                          |
              |
         __________                      ________  +------------+
        /          \              ____  /          |  Worker 1  |
       |   Varda    |  ________  /    \  ________  +------------+
       |____________|           /      \           |  Worker 2  |
       |            |          | Broker | _______  +------------+
       |  REST API  |           \      /           |  Worker 3  |
        \__________/             \____/            +------------+
                                                         ...
              |
              |
         __________
        /          \
       |   Client   |
        \__________/


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


Frequency calculation
---------------------

Only take samples into account with covered regions (to rule out population
studies).


Binning of regions and observations
-----------------------------------

Todo. UCSC binning scheme.


Security
--------

Todo: Add a page on security to the Managing Varda section.

Authentication via HTTP Basic Authentication, or API tokens, so only use with
SSL.


Sample state
------------

A sample can be either *active* or *inactive* (default). An inactive sample is
ignored in any frequency calculations.

Importing data sources is only possible for inactive samples. A sample cannot
be made active while any data source is being imported for that sample. Users
can only make a sample active, not inactive.
