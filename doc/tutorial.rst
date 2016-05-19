.. _tutorial:

Tutorial
========

This tutorial shows you how to setup Varda with the `Aulë`_ web interface and
`Manwë`_ command line client, and how to import and query an example dataset.

The example dataset is taken from the Varda unit tests and is limited to the
first 200,000 bases of human chromosome 20 (GRCh37/hg19).

.. highlight:: none


.. _tutorial-varda:

Setting up Varda
----------------

Follow the :ref:`installation instructions <install>` to install
Varda. Configure Varda to use ``hg19.fa`` in the ``tests/data`` directory as
reference genome and enable `cross-origin resource sharing (CORS)
<https://en.wikipedia.org/wiki/Cross-origin_resource_sharing>`_ (this allows
Aulë to communicate with Varda). The Varda configuration file may look
something like this:

.. code-block:: python

    DATA_DIR = 'data'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///varda.db'
    BROKER_URL = 'redis://'
    CELERY_RESULT_BACKEND = 'redis://'
    GENOME = 'tests/data/hg19.fa'
    CORS_ALLOW_ORIGIN = '*'

.. seealso::

   :ref:`config`
     More information on available configuration settings.

Start Varda and a Celery worker node as described in :ref:`run`::

    $ varda debugserver

and::

    $ celery worker -A varda.worker.celery -l info

Opening `<http://127.0.0.1:5000/genome>`_ in your browser should now show you
a JSON representation of the reference genome configuration.


.. _tutorial-aule:

Setting up Aulë
---------------

Get the source code for `Aulë`_, configure it to use `MyGene.info
<http://mygene.info/>`_ with GRCh37/hg19, and run it::

    $ git clone https://github.com/varda/aule.git
    $ cd aule
    $ nano config.js
    AULE_CONFIG = {
      BASE: '/',
      API_ROOT: 'http://127.0.0.1:5000/',
      PAGE_SIZE: 50,
      MANY_PAGES: 13,
      MY_GENE_INFO: {
        species: 'human',
        exons_field: 'exons_hg19'
      }
      MY_GENE_INFO: null
    };
    $ npm install
    $ npm run dev

You can now open `<http://localhost:8000/>`_ in your browser, which should
show you the Aulë homepage. Login with ``admin`` and the password you choose
during Varda setup.


.. _tutorial-manwe:

Setting up Manwë
----------------

`Manwë`_ authenticates with the Varda API using a token. You can generate a
token in the Aulë web interface by choosing *API tokens* in the menu and
clicking *Generate API token*. Copy the token by clicking *Show token*.

Install Manwë and create a configuration file with the token you just
created::

    $ pip install manwe
    $ nano manwe.cfg
    API_ROOT = 'http://127.0.0.1:5000'
    TOKEN = 'c7fa8780025c8efa5077567434e0fcb56274fbb0'

Verify that everything is setup correctly by listing all Varda users::

    $ manwe users list -c manwe.cfg
    User:   /users/1
    Name:   Admin User
    Login:  admin
    Roles:  admin

.. note:: Instead of including ``-c manwe.cfg`` in every invocation, you can
          also copy this file to ``~/.config/manwe/config`` (``config`` should
          be the name of the file) where Manwë will pick it up automatically.


.. _tutorial-import-exome:

Importing exome sequencing data
-------------------------------

Let's import an example set of variant calls from an exome sequencing
experiment. The file ``tests/data/exome.vcf`` contains some variant calls on
chromosome 20 for one individual and ``tests/data/exome.vcf`` contains regions
on chromosome 20 where the sequencing was deep enough (or of high enough
quality) to do variant calling::

    $ cat tests/data/exome.vcf
    ##fileformat=VCFv4.1
    ##samtoolsVersion=0.1.16 (r963:234)
    ...
    #CHROM  POS     ID  REF    ALT  QUAL  FILTER  INFO  FORMAT    -
    chr20   76962   .   T      C    173   .       ...   GT:PL:GQ  0/1:203,0,221:99
    chr20   126159  .   ACAAA  A    217   .       ...   GT:PL:GQ  0/1:255,0,255:99
    chr20   126313  .   CCC    C    126   .       ...   GT:PL:GQ  0/1:164,250,0:99
    ...
    $ cat tests/data/exome.bed
    chr206811268631
    chr207658177410
    chr209002590400
    ...

.. note:: For any real data you import, it is best to always include both the
          variant calls in VCF format *and* a BED file of regions to
          include. This makes it possible for Varda to calculate accurate
          variant frequencies, also on regions that are not covered by some
          experiments.

Import the data as follows::

    $ manwe samples import --vcf tests/data/exome.vcf --bed tests/data/exome.bed \
    >     -l -w 'Exome sample'
    Added sample: /samples/1
    Added data source: /data_sources/1
    Started variation import: /variations/1
    Added data source: /data_sources/2
    Started coverage import: /coverages/1
    [################################] 100/100 - 00:00:02
    Imported variations and coverages for sample: /samples/1

.. note:: The ``-l`` argument instructs Varda to use the ``PL`` column instead
          of the ``GT`` column to derive the genotypes. Use it when variant
          calling was done with Samtools.

Since Varda supports importing data for a sample in multiple steps, new
samples are inactive by default to prevent using them in frequency
calculations until everything is complete. Activate the sample you just
imported with::

    $ manwe samples activate /samples/1
    Activated sample: /samples/1

If you go back to the Aulë web interface and choose *Samples* in the menu, you
should see the exome sample you just imported.


.. _tutorial-import-aggregate:

Importing aggregate data from 1000 Genomes
------------------------------------------

Sometimes it makes sense to calculate variant frequencies within a dataset
separately, as opposed to global frequencies over all datasets. An example
might be a large public population study such as the 1000 Genomes
project. Varda allows you to import a dataset like this without providing
coverage data (i.e., the BED file).

The ``tests/data/1kg.vcf`` file contains a subset of variant calls from the
1000 Genomes project over 1092 individuals. Import it as follows::

    $ manwe samples import --vcf ../varda/tests/data/1kg.vcf -s 1092 -p \
    >     --no-coverage-profile -w '1000 Genomes'
    Added sample: /samples/2
    Added data source: /data_sources/3
    Started variation import: /variations/2
    [################################] 100/100 - 00:00:02
    Imported variations and coverages for sample: /samples/2
    $ manwe samples activate /samples/2
    Activated sample: /samples/2

.. note:: Samples imported without coverage profile are automatically excluded
          from global variant frequency calculations. Instead, they may be
          queried separately.


.. _tutorial-query:

Querying variant frequencies
----------------------------

Aulë allows for some ad-hoc querying of variant frequencies globally and per
sample, as well as by variant, by region and by transcript region. Choose
*By region* in the menu and set:

Query:
  *Global query*
Chromosome:
  *chr20*
Region begin:
  *1*
Region end:
  *200000*

This should show you the variants from the exome sequencing example, all with
frequency 1.0 and *N=1* (since it's the only sample used in the calculation).

You can run the same query on the 1000 Genomes data by setting:

Query:
  *Sample query (1000 Genomes)*

As an alternative to setting the region manually, you can also choose *By
transcript* in the menu and select a region based on a gene transcript. The
exome example has two variants in the DEFB126 gene. You can select it by
clicking on *Choose a transcript* and typing ``DEFB126``.


.. _tutorial-annotate:

Annotating variants
-------------------

The ad-hoc frequency queries with Aulë are nice for one-time lookups, but you
would presumably also want to automate this on a larger scale. Manwë allows
you to annotate local VCF or BED files with variant frequencies by supplying a
list of queries::

    $ manwe annotate-vcf -q GLOBAL '*' -q 1KG 'sample:/samples/2' -w \
    >     tests/data/exome.vcf
    Added data source: /data_sources/4
    Started annotation: /annotations/1
    [################################] 100/100 - 00:00:02
    Annotated VCF file: /data_sources/5
    $ manwe data-sources download /data_sources/5 > exome.annotated.vcf.gz

The resulting VCF file is annotated with several fields in the ``INFO``
column.


.. _Aulë: https://github.com/varda/aule
.. _Manwë: https://github.com/varda/manwe
