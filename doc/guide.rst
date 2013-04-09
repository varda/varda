.. _guide:

User's guide
============

.. todo:: Structure this guide, it's an incomplete random collection of
   paragraphs.


.. _guide-coverage:

Variant frequencies and genomic coverage
----------------------------------------

Todo.


.. _guide-roles:

User roles
----------

Todo.


.. _guide-activation:

Sample activation
-----------------

Todo.


.. _guide-checksums:

Duplication of data
-------------------

Todo.

Calculating checksums of all imported data is used as a measure to prevent the
same data to be imported twice. Of course, this is quite a weak measure in
that it can easily be circumvented, so its main value lies in preventing
accidental duplicate imports.


.. _guide-trading:

A model for trading data
------------------------

For certain use cases it may be desirable that variant frequencies can only be
retrieved from Varda by annotating variants that are imported in Varda (see
:ref:`Shared database between several groups <intro-use-case-groups>`). In
this model variant observations are traded for variant frequencies.

Varda facilitates this with the `trader` role. The `trader` role gives a user
permission to annotate a data source, but only if that data source has been
imported as part of an active sample.

See :ref:`guide-roles` for more information on roles.


.. _guide-anonymity:

Sample anonymity
----------------

Todo. Only global frequencies, except for public samples. Of course depending
on the number of samples in the database. See :ref:`guide-pooling`.


.. _guide-pooling:

Pooling samples
---------------

.. highlight:: bash

By design, Varda cannot be queried in a way to reconstruct the genotype for a
specific sample, unless that sample is explicitely marked as being public (see
:ref:`guide-anonymity`). However, the sample genotypes are stored in the Varda
database and for various reasons you might not be comfortable with that. This
can be addressed by `pooling` samples before sending them to Varda, a trick
that loses individual genotypes at no cost in functionality.

The idea is to mix the data from several samples together and send the result
to Varda as one sample. Variant frequency calculations are not affected by
this, yet individual genotypes are irrevocably scrambled. There are different
ways to mix variant calls from different samples, you can find some examples
below.

Besides variant calls, coverage information could also be mixed. However, it
is probably not worth the trouble since this is not sensitive data.

.. note:: The effect of pooling is related to the number of samples. The
   greater the pool size, the better it works.


Example: merge single-sample VCF files
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Starting with a VCF file per sample, one can simply concatenate all of them
(minus the headers) and sort the result by chromosomal position. The resulting
file looks like a single-sample VCF file, just with many more variant calls in
it. ::

    $ (grep '^#' 1.vcf; grep -hv '^#' *.vcf | sort -k 1,1 -k 2n,2) > pooled.vcf


Example: shuffle a multi-sample VCF file
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you already have a multi-sample VCF file containing variant calls for your
samples, you can randomize the sample columns repeatedly for each line. The
resulting file has lost individual genotypes, but contains the same variant
frequency information. ::

    $ grep '^#' samples.vcf > shuffled.vcf
    $ paste \
        <(grep -v '^#' samples.vcf | cut -f 1-9) \
        <(grep -v '^#' samples.vcf | cut -f 10- \
          | xargs -L 1 bash -c 'shuf -e $* | paste -s' _) \
        >> shuffled.vcf
