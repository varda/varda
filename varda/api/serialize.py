"""
API model serializers.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from functools import wraps

from flask import url_for

from ..models import Annotation, Coverage, DataSource, InvalidDataSource, Sample, User, Variation
from ..tasks import TaskError
from .errors import ActivationFailure, ValidationError


# Dispatch table for the serialize function below.
_serializers = []


def serializes(model):
    """
    Decorator to specify that a function creates a representation for a
    certain model.
    """
    def serializes_model(serializer):
        _serializers.append( (model, serializer) )
        @wraps(serializer)
        def wrapped_serializer(*args, **kwargs):
            return serializer(*args, **kwargs)
        return wrapped_serializer
    return serializes_model


# Note that the docstrings of the `serialize_*` functions below are included
# verbatim in the REST API documentation.


@serializes(User)
def serialize_user(instance, expand=None):
    """
    A user is represented as an object with the following fields:

    * **uri** (`string`) - URI for this user.
    * **name** (`string`) - Human readable name.
    * **login** (`string`) - User login used for identification.
    * **roles** (`list of string`) - Roles this user has.
    * **added** (`string`) - Date and time this user was added.

    Example representation:

    .. sourcecode:: json

        {
          "uri": "/users/fred",
          "name": "Frederick Sanger",
          "login": "fred",
          "roles": ["admin"],
          "added": "2012-11-23T10:55:12.776706"
        }
    """
    return {'uri':   url_for('.users_get', login=instance.login),
            'name':  instance.name,
            'login': instance.login,
            'roles': list(instance.roles),
            'added': str(instance.added.isoformat())}


@serializes(DataSource)
def serialize_data_source(instance, expand=None):
    """
    A data source is represented as an object with the following fields:

    * **uri** (`string`) - URI for this data source.
    * **user_uri** (`string`) - URI for the data source :ref:`owner <api_users>`.
    * **annotations_uri** (`string`) - URI for the data source :ref:`annotations <api_annotations>`.
    * **data_uri** (`string`) - URI for the data.
    * **name** (`string`) - Human readable name.
    * **filetype** (`string`) - Data filetype.
    * **gzipped** (`boolean`) - Whether or not data is compressed.
    * **added** (`string`) - Date this data source was added.

    Example representation:

    .. sourcecode:: json

        {
          "uri": "/data_sources/23",
          "user_uri": "/users/fred",
          "annotations_uri": "/data_sources/23/annotations",
          "data_uri": "/data_sources/23/data",
          "name": "1KG chromosome 20 SNPs",
          "filetype": "vcf",
          "gzipped": true,
          "added": "2012-11-23T10:55:12.776706"
        }
    """
    return {'uri':             url_for('.data_sources_get', data_source_id=instance.id),
            'user_uri':        url_for('.users_get', login=instance.user.login),
            'annotations_uri': url_for('.annotations_list', data_source_id=instance.id),
            'data_uri':        url_for('.data_sources_data', data_source_id=instance.id),
            'name':            instance.name,
            'filetype':        instance.filetype,
            'gzipped':         instance.gzipped,
            'added':           str(instance.added.isoformat())}


@serializes(Variation)
def serialize_variation(instance, expand=None):
    """
    A set of observations is represented as an object with the following
    fields:

    * **uri** (`string`) - URI for this set of observations.
    * **sample_uri** (`string`) - URI for the :ref:`sample <api_samples>`.
    * **data_source_uri** (`string`) - URI for the :ref:`data source <api_data_sources>`.
    * **imported** (`boolean`) - Whether or not this set of observations is imported.

    Example representation:

    .. sourcecode:: json

        {
          "uri": "/samples/3/variations/17",
          "sample_uri": "/samples/3",
          "data_source_uri": "/data_sources/23",
          "imported": true
        }
    """
    expand = expand or []
    serialization = {'uri':             url_for('.variations_get', sample_id=instance.sample_id, variation_id=instance.id),
                     'sample_uri':      url_for('.samples_get', sample_id=instance.sample_id),
                     'data_source_uri': url_for('.data_sources_get', data_source_id=instance.data_source_id),
                     'imported':        instance.imported}
    if 'data_source' in expand:
        serialization.update(data_source=serialize(instance.data_source))
    return serialization


@serializes(Coverage)
def serialize_coverage(instance, expand=None):
    """
    A set of regions is represented as an object with the following fields:

    * **uri** (`string`) - URI for this set of regions.
    * **data_source_uri** (`string`) - URI for the :ref:`data source <api_data_sources>`.

    Example representation:

    .. sourcecode:: json

        {
          "uri": "/samples/3/coverages/11",
          "data_source_uri": "/data_sources/24"
        }
    """
    return {'uri':             url_for('.coverages_get', sample_id=instance.sample_id, coverage_id=instance.id),
            'data_source_uri': url_for('.data_sources_get', data_source_id=instance.data_source_id)}


@serializes(Annotation)
def serialize_annotation(instance, expand=None):
    """
    An annotation is represented as an object with the following fields:

    * **uri** (`string`) - URI for this annotation.
    * **original_data_source_uri** (`string`) - URI for the original :ref:`data source <api_data_sources>`.
    * **annotated_data_source_uri** (`string`) - URI for the annotated :ref:`data source <api_data_sources>`.

    Example representation:

    .. sourcecode:: json

        {
          "uri": "/data_sources/23/annotations/2",
          "original_data_source_uri": "/data_sources/23",
          "annotated_data_source_uri": "/data_sources/57"
        }
    """
    return {'uri':                       url_for('.annotations_get', data_source_id=instance.original_data_source_id, annotation_id=instance.id),
            'original_data_source_uri':  url_for('.data_sources_get', data_source_id=instance.original_data_source_id),
            'annotated_data_source_uri': url_for('.data_sources_get', data_source_id=instance.annotated_data_source_id)}


@serializes(Sample)
def serialize_sample(instance, expand=None):
    """
    A sample is represented as an object with the following fields:

    * **uri** (`string`) - URI for this sample.
    * **user_uri** (`string`) - URI for the sample :ref:`owner <api_users>`.
    * **variations_uri** (`string`) - URI for the :ref:`sets of observations <api_variations>`.
    * **coverages_uri** (`string`) - URI for the :ref:`sets of regions <api_coverages>`.
    * **name** (`string`) - Human readable name.
    * **pool_size** (`integer`) - Number of individuals.
    * **public** (`boolean`) - Whether or not this sample is public.
    * **added** (`string`) - Date and time this sample was added.

    Example representation:

    .. sourcecode:: json

        {
          "uri": "/samples/3",
          "user_uri": "/users/fred",
          "variations_uri": "/samples/3/variations",
          "coverages_uri": "/samples/3/coverages",
          "name": "1KG phase 1 release",
          "pool_size": 1092,
          "public": true,
          "added": "2012-11-23T10:55:12.776706"
        }
    """
    return {'uri':                    url_for('.samples_get', sample_id=instance.id),
            'user_uri':               url_for('.users_get', login=instance.user.login),
            'variations_uri':         url_for('.variations_list', sample_id=instance.id),
            'coverages_uri':          url_for('.coverages_list', sample_id=instance.id),
            'name':                   instance.name,
            'pool_size':              instance.pool_size,
            'public':                 instance.public,
            'added':                  str(instance.added.isoformat())}


@serializes(ActivationFailure)
@serializes(InvalidDataSource)
@serializes(TaskError)
def serialize_exception(instance, expand=None):
    """
    An error is represented as an object with the following fields:

    * **code** (`string`) - Error code (todo: document error codes).
    * **message** (`string`) - Human readable error message.

    Example representation:

    .. sourcecode:: json

        {
          "code": "unknown_filetype",
          "message": "Data source filetype \"gff\" is unknown"
        }
    """
    return {'code':    instance.code,
            'message': instance.message}


@serializes(ValidationError)
def serialize_validation_error(instance, expand=None):
    """
    A validation error is represented like other exceptions, but with the
    error code fixed as ``bad_request``.
    """
    return {'code':    'bad_request',
            'message': instance.message}


def serialize(instance, expand=None):
    """
    Create a RESTfull representation of an object as dictionary.

    This function dispatches to a specific serializer function depending on
    the type of object at hand.

    .. note:: Returns ``None`` if no serializer was found.
    .. note:: I don't think this construction of creating serializations is
        especially elegant, but it gets the job done and I really don't want
        any functionality for representations in the models themselves.
    .. todo:: Document `expand` keyword argument.
    """
    for model, serializer in _serializers:
        if isinstance(instance, model):
            return serializer(instance, expand=expand)
