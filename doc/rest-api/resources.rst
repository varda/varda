.. _api-resources:

REST API resources
==================

.. _api-resources-root:

API root
--------

The API root resource contains links to top-level resources in addition to a
server status code.

.. autofunctiondoc:: varda.api.views.root_serialize

.. http:get:: /

   .. autofunctiondoc:: varda.api.views.root_get


.. _api-resources-authentication:

Authentication
--------------

This resource reflects the current authentication state.

.. autofunctiondoc:: varda.api.views.authentication_serialize

.. http:get:: /

   .. autofunctiondoc:: varda.api.views.authentication_get


.. _api-resources-genome:

Genome
------

If the server is configured with a reference genome, this resource lists its
chromosomes.

.. autofunctiondoc:: varda.api.views.genome_serialize

.. http:get:: /

   .. autofunctiondoc:: varda.api.views.genome_get


.. _api-resources-annotations:

Annotations
-----------

.. autodatadoc:: varda.api.views.annotations_resource

.. automethoddoc:: varda.api.views.annotations_resource.serialize


.. _api-resources-annotations-collection:

Collection
^^^^^^^^^^

.. seealso:: :ref:`Collection resources <api-collection-resources>`

.. http:get:: /annotations/

   .. automethoddoc:: varda.api.views.annotations_resource.list_view

.. http:post:: /annotations/

   .. automethoddoc:: varda.api.views.annotations_resource.add_view


.. _api-resources-annotations-instances:

Instances
^^^^^^^^^

.. http:get:: /annotations/<id>

   .. automethoddoc:: varda.api.views.annotations_resource.get_view

.. http:patch:: /annotations/<id>

   .. automethoddoc:: varda.api.views.annotations_resource.edit_view


.. _api-resources-coverages:

Coverages
---------

.. autodatadoc:: varda.api.views.coverages_resource

.. automethoddoc:: varda.api.views.coverages_resource.serialize


.. _api-resources-coverages-collection:

Collection
^^^^^^^^^^

.. seealso:: :ref:`Collection resources <api-collection-resources>`

.. http:get:: /coverages/

   .. automethoddoc:: varda.api.views.coverages_resource.list_view

.. http:post:: /coverages/

   .. automethoddoc:: varda.api.views.coverages_resource.add_view


.. _api-resources-coverages-instances:

Instances
^^^^^^^^^

.. http:get:: /coverages/<id>

   .. automethoddoc:: varda.api.views.coverages_resource.get_view

.. http:patch:: /coverages/<id>

   .. automethoddoc:: varda.api.views.coverages_resource.edit_view


.. _api-resources-data-sources:

Data sources
------------

.. autodatadoc:: varda.api.views.data_sources_resource

.. automethoddoc:: varda.api.views.data_sources_resource.serialize


.. _api-resources-data-sources-collection:

Collection
^^^^^^^^^^

.. seealso:: :ref:`Collection resources <api-collection-resources>`

.. http:get:: /data_sources/

   .. automethoddoc:: varda.api.views.data_sources_resource.list_view

.. http:post:: /data_sources/

   .. automethoddoc:: varda.api.views.data_sources_resource.add_view


.. _api-resources-data-sources-instances:

Instances
^^^^^^^^^

.. http:get:: /data_sources/<id>

   .. automethoddoc:: varda.api.views.data_sources_resource.get_view

.. http:patch:: /data_sources/<id>

   .. automethoddoc:: varda.api.views.data_sources_resource.edit_view


.. _api-resources-data-sources-blobs:

Blobs
^^^^^

.. http:get:: /data_sources/<id>/data

   .. automethoddoc:: varda.api.views.data_sources_resource.data_view


.. _api-resources-samples:

Samples
-------

.. autodatadoc:: varda.api.views.samples_resource

.. automethoddoc:: varda.api.views.samples_resource.serialize


.. _api-resources-samples-collection:

Collection
^^^^^^^^^^

.. seealso:: :ref:`Collection resources <api-collection-resources>`

.. http:get:: /samples/

   .. automethoddoc:: varda.api.views.samples_resource.list_view

.. http:post:: /samples/

   .. automethoddoc:: varda.api.views.samples_resource.add_view


.. _api-resources-samples-instances:

Instances
^^^^^^^^^

.. http:get:: /samples/<id>

   .. automethoddoc:: varda.api.views.samples_resource.get_view

.. http:patch:: /samples/<id>

   .. automethoddoc:: varda.api.views.samples_resource.edit_view


.. _api-resources-tokens:

Tokens
------

.. autodatadoc:: varda.api.views.tokens_resource

.. automethoddoc:: varda.api.views.tokens_resource.serialize


.. _api-resources-tokens-collection:

Collection
^^^^^^^^^^

.. seealso:: :ref:`Collection resources <api-collection-resources>`

.. http:get:: /tokens/

   .. automethoddoc:: varda.api.views.tokens_resource.list_view

.. http:post:: /tokens/

   .. automethoddoc:: varda.api.views.tokens_resource.add_view


.. _api-resources-tokens-instances:

Instances
^^^^^^^^^

.. http:get:: /tokens/<id>

   .. automethoddoc:: varda.api.views.tokens_resource.get_view

.. http:patch:: /tokens/<id>

   .. automethoddoc:: varda.api.views.tokens_resource.edit_view


.. _api-resources-users:

Users
-----

.. autodatadoc:: varda.api.views.users_resource

.. automethoddoc:: varda.api.views.users_resource.serialize


.. _api-resources-users-collection:

Collection
^^^^^^^^^^

.. seealso:: :ref:`Collection resources <api-collection-resources>`

.. http:get:: /users/

   .. automethoddoc:: varda.api.views.users_resource.list_view

.. http:post:: /users/

   .. automethoddoc:: varda.api.views.users_resource.add_view


.. _api-resources-users-instances:

Instances
^^^^^^^^^

.. http:get:: /users/<id>

   .. automethoddoc:: varda.api.views.users_resource.get_view

.. http:patch:: /users/<id>

   .. automethoddoc:: varda.api.views.users_resource.edit_view


.. _api-resources-variants:

Variants
--------

.. autodatadoc:: varda.api.views.variants_resource

.. automethoddoc:: varda.api.views.variants_resource.serialize


.. _api-resources-variants-collection:

Collection
^^^^^^^^^^

.. seealso:: :ref:`Collection resources <api-collection-resources>`

.. http:get:: /variants/

   .. automethoddoc:: varda.api.views.variants_resource.list_view

.. http:post:: /variants/

   .. automethoddoc:: varda.api.views.variants_resource.add_view


.. _api-resources-variants-instances:

Instances
^^^^^^^^^

.. http:get:: /variants/<id>

   .. automethoddoc:: varda.api.views.variants_resource.get_view


.. _api-resources-variations:

Variations
----------

.. autodatadoc:: varda.api.views.variations_resource

.. automethoddoc:: varda.api.views.variations_resource.serialize


.. _api-resources-variations-collection:

Collection
^^^^^^^^^^

.. seealso:: :ref:`Collection resources <api-collection-resources>`

.. http:get:: /variations/

   .. automethoddoc:: varda.api.views.variations_resource.list_view

.. http:post:: /variations/

   .. automethoddoc:: varda.api.views.variations_resource.add_view


.. _api-resources-variations-instances:

Instances
^^^^^^^^^

.. http:get:: /variations/<id>

   .. automethoddoc:: varda.api.views.variations_resource.get_view

.. http:patch:: /variations/<id>

   .. automethoddoc:: varda.api.views.variations_resource.edit_view
