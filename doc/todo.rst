Todo list
=========

These are some general todo notes. More specific notes can be found by
grepping the source code for ``Todo``.

* Authentication using single-purpose issued tokens in addition to
  login/password. Have a notice in the docs to only deploy on HTTPS and close
  port 80 entirely (to prevent any requests with credentials being sent)
  instead of redirecting to HTTPS.

* Complete docs, including REST API docs.

* More strict validation of user input, especially file uploads (max file size
  and contents).

* Implement caching control headers.

* Implement HEAD requests.

* Better organised and more comprehensive test suite.

* Throtling.

* Better rights/roles model.

* Support input in BCF2 format.

* Have a look at supporting the `gVCF format <https://sites.google.com/site/gvcftools/)>`_.

* Attach tags (e.g. 'exome', 'illumina', 'cancer'). Not sure if they should be
  separate resources on their own, or just string arguments.

* Possibility to contact submitter of an observation.

* Have a maintenance and/or read-only mode, probably with HTTP redirects.

* Store phasing info, for example by numbering each allele (uniquely within a
  sample) and store the allele number with observations.

* Support bigBed format.

* What to do for variants where we have more observations than coverage? We
  could have a check in sample activation, but would we really like to
  enforce this?

* Enforce active property of sample. Changing anything means deactivating
  (automatically or manually?) and activating can only be done if everything
  is ok (no duplicated imports, everything has been imported, etc).
  Also, should owners be allowed to delete their imports and samples?

* Move region binning to its own package.

* Fallback modes to accomodate browsing the API with a standard web browser,
  e.g., query string alternative to pagination with Accept-Range headers.
  Perhaps this can be optional and implemented by patching the Request object
  before it reaches the API code.

* Implement Cross-origin resource sharing (CORS) to enable serving Aulë from
  another domain.

* We currently store variants as `(position, reference, observed)` and regions
  as `(begin, end)` where all positioning is one-based and inclusive. An
  alternative is implemented in the ``observation-format`` git branch where
  all positioning is zero-based and open-ended and variants are stored as
  `(begin, end, observed)`.

  Here are some advantages of the alternative representation:

  - If a reference genome is configured, the `reference` field is superfluous
    and we can do with defining just a region.
  - Zero-based and open-ended positioning follows Python indexing and slicing
    notation as well as the BED format.
  - Insertions are perhaps more naturally modelled by giving an empty region
    on the reference genome.
  - Overlaps between regions and variants are easier to query for with `begin`
    and `end` fields.

  But it also has some downsides:

  - The current variant representation follows existing practices and
    therefore all interfaces to the outside world more closely.
  - If there is no reference genome configured, we don't have a complete
    definition of our variants.
  - It means a lot of conversions between representations.

  Note that the current representation isn't following VCF, since VCF requires
  both the `reference` and `observed` sequences to be non-empty. However, by
  normalizing (and also anticipating other sources than VCF) we trim every
  sequence as much as possible.

  For now we think it is best to stick with the current representations, but
  this is still somewhat up for discussion.

* Have a section in the docs describing the unit tests. Also note that the
  unit tests use the first 200,000 bases of chromosome 19 as a reference
  genome.

* Refactor how we handle Celery tasks. Don't store the task uuid in the
  database. Probably also create the resulting resource in the task, not
  before starting the task like we do now.

  A running task should be monitored and, when finished, it points to the
  resulting resource.

  We can probably still list running tasks even though we don't store them
  in the database, following `what Flower does
  <https://github.com/mher/flower/blob/master/flower/models.py#L104>`_.
  This will only work when sending task events is enabled (``-E`` option to
  ``celeryd``). Also have a look at `CELERY_SEND_EVENTS` and
  `CELERY_SEND_TASK_SENT_EVENT` `configuration options
  <http://docs.celeryproject.org/en/latest/configuration.html#events>`_.
  As `this post suggests
  <http://stackoverflow.com/questions/15575826/how-to-inspect-and-cancel-celery-tasks-by-task-name>`_,
  we probably also have to explicitely monitor the events.

* See if `this issue
  <https://github.com/mitsuhiko/flask-sqlalchemy/issues/144>`_ affects us.

* For simplicity, we are currently storing `homozygous` vs `heterozygous` for
  each alternate call. Shouldn't we actually be storing the genotype, like
  `0/1` vs `1/1` (in reporting, we could include `0/0`)? It is more general.

  I can think of two reasons why we choose not to store genotypes. The first
  is that we don't have reference calls (but we could simply omit `0/0`). The
  second is that we don't have a guarantee that a given chromosome was called
  using the same ploidity. Therefore, we could for example have genotypes from
  different samples on the Y chromosome as `0/0`, `0/1`, `1/1` versus `0`,
  `1`. We could report these as-is, or merge them to the highest ploidity
  which would be incorrect in this case. Or we store the ploidity for each
  chromosome system-wide.

* Having a pool size per sample is not granular enough in some situations. For
  example, the `1KG phase1 integrated call sets
  <http://ftp.1000genomes.ebi.ac.uk/vol1/ftp/phase1/analysis_results/integrated_call_sets/>`_
  are over 1092 individuals for most chromosomes, but over 1083 and 535 for
  the mitochondrial genome and chromosome Y, respectively.
  Not sure if we can really solve this easily, since having a pool size per
  variation/coverage will not work for samples with coverage.
