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
* Delete resources (have to think about cascading or not).
* Support bigBed format.
* What to do for variants where we have more observations than coverage? We
  could have a check in sample activation, but would we really like to
  enforce this?
* Enforce active property of sample. Changing anything means deactivating
  (automatically or manually?) and activating can only be done if everything
  is ok (no duplicated imports, everything has been imported, etc).
* Move region binning to its own package.
* Fallback modes to accomodate browsing the API with a standard web browser,
  e.g., query string alternative to pagination with Accept-Range headers.
  Perhaps this can be optional and implemented by patching the Request object
  before it reaches the API code.
* Implement Cross-origin resource sharing (CORS) to enable serving Aulë from
  another domain.
