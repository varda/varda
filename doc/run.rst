.. _run:

Running Varda
=============

.. highlight:: bash

Varda comes with a built-in test server that's useful for development and
debugging purposes. You can start it like this::

    $ varda debugserver
     * Running on http://127.0.0.1:5000/

You can now point your webbrowser to the URL that is printed and see a json-
encoded status page.

This won't get you far in production though and there are many other
possibilities for deploying Varda. Recommended is the `Gunicorn`_ WSGI HTTP
server, which you could use like this::

    $ gunicorn varda:create_app\(\) -w 4 -t 600 --max-requests=1000

See the Gunicorn website for documentation.

Varda distributes long-running tasks (such as importing and annotating variant
files) using `Celery`_. For running such tasks, you have to start at least one
Celery worker node::

    $ celery worker -A varda.worker.celery -l info --maxtasksperchild=4

     -------------- celery@hue v3.0.17 (Chiastic Slide)
    ---- **** -----
    --- * ***  * -- [Configuration]
    -- * - **** --- . broker:      redis://localhost:6379//
    - ** ---------- . app:         varda:0x3602c50
    - ** ---------- . concurrency: 8 (processes)
    - ** ---------- . events:      OFF (enable -E to monitor this worker)
    - ** ----------
    - *** --- * --- [Queues]
    -- ******* ---- . celery:      exchange:celery(direct) binding:celery
    --- ***** -----

    [Tasks]
      . varda.tasks.import_coverage
      . varda.tasks.import_variation
      . varda.tasks.ping
      . varda.tasks.write_annotation

    [2013-04-05 17:39:59,882: WARNING/MainProcess] celery@hue ready.
    [2013-04-05 17:39:59,886: INFO/MainProcess] consumer: Connected to redis://localhost:6379//.


.. _Celery: http://www.celeryproject.org/
.. _Gunicorn: http://gunicorn.org/
