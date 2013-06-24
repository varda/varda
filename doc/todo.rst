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
