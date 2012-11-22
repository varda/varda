Todo list
=========

* Import data source directly from URL without uploading.
* Everything must be in UTF8.
* Use Alembic for database migrations.
* Other types of authentication (OAuth).
* Better docs.
* Add setup.py with ``entry_points={'console_scripts': ['varda-manage = varda.manage:main']}``.
* Validate user input, especially file uploads (max file size).
* Less granular API, e.g. way to import and annotate sample with fewer requests.
* Use accept HTTP headers in the API.
* More comprehensive test suite.


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


Nesting in API representations
------------------------------

Representations of resources can sometimes be nested arbitrarily
deeply.

One extreme would be to only represent nested resources by their URL, the
other extreme would be to always give the full JSON representation of the
nested resource (unless the nesting is infinitely deep of course). A
possible solution is to add a ``?depth=N`` query parameter to view URLs, where
``N`` would be how deep to expand URLs with JSON representations. A nice
implementation for this on the server side will require some thinking...

Also see `this discussion <http://news.ycombinator.com/item?id=3491227>`_.


Ranges in API collection requests
---------------------------------

Implement pagination for collection representations, perhaps with HTTP range
headers. This is related to sorting and filtering. See e.g.
`this document <http://dojotoolkit.org/reference-guide/quickstart/rest.html>`_.
