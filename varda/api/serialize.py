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
def serialize_user(instance):
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
          "uri": "/users/1",
          "name": "Frederick Sanger",
          "login": "fred",
          "roles": ["admin"],
          "added": "2012-11-23T10:55:12.776706"
        }
    """
    return {'uri':   url_for('.user_get', user=instance.id),
            'name':  instance.name,
            'login': instance.login,
            'roles': list(instance.roles),
            'added': str(instance.added.isoformat())}


@serializes(DataSource)
def serialize_data_source(instance):
    """
    A data source is represented as an object with the following fields:

    * **uri** (`string`) - URI for this data source.
    * **user** (:ref:`user <api_users>`) - Data source owner.
    * **data** (`object`) - Object with one field: **uri** (`string`) - URI for the data.
    * **name** (`string`) - Human readable name.
    * **filetype** (`string`) - Data filetype.
    * **gzipped** (`boolean`) - Whether or not data is compressed.
    * **added** (`string`) - Date this data source was added.

    Example representation:

    .. sourcecode:: json

        {
          "uri": "/data_sources/23",
          "user_uri": "/users/1",
          "data_uri": "/data_sources/23/data",
          "name": "1KG chromosome 20 SNPs",
          "filetype": "vcf",
          "gzipped": true,
          "added": "2012-11-23T10:55:12.776706"
        }
    """
    return {'uri':             url_for('.data_sources_get', data_source=instance.id),
            'user_uri':        url_for('.users_get', user=instance.user.id),
            'data_uri':        url_for('.data_sources_data', data_source=instance.id),
            'name':            instance.name,
            'filetype':        instance.filetype,
            'gzipped':         instance.gzipped,
            'added':           str(instance.added.isoformat())}


@serializes(Variation)
def serialize_variation(instance):
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
    return {'uri':             url_for('.variations_get', variation=instance.id),
            'sample_uri':      url_for('.samples_get', sample=instance.sample_id),
            'data_source_uri': url_for('.data_sources_get', data_source=instance.data_source_id),
            'imported':        instance.task_done}


@serializes(Coverage)
def serialize_coverage(instance):
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
    return {'uri':             url_for('.coverages_get', coverage=instance.id),
            'sample_uri':      url_for('.samples_get', sample=instance.sample_id),
            'data_source_uri': url_for('.data_sources_get', data_source=instance.data_source_id),
            'imported':        instance.task_done}


@serializes(Annotation)
def serialize_annotation(instance):
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
    return {'uri':                       url_for('.annotations_get', annotation=instance.id),
            'original_data_source_uri':  url_for('.data_sources_get', data_source=instance.original_data_source_id),
            'annotated_data_source_uri': url_for('.data_sources_get', data_source=instance.annotated_data_source_id),
            'written':                   instance.task_done}


@serializes(Sample)
def serialize_sample(instance):
    """
    A sample is represented as an object with the following fields:

    * **uri** (`string`) - URI for this sample.
    * **user_uri** (`string`) - URI for the sample :ref:`owner <api_users>`.
    * **name** (`string`) - Human readable name.
    * **pool_size** (`integer`) - Number of individuals.
    * **public** (`boolean`) - Whether or not this sample is public.
    * **added** (`string`) - Date and time this sample was added.

    Example representation:

    .. sourcecode:: json

        {
          "uri": "/samples/3",
          "user_uri": "/users/1",
          "name": "1KG phase 1 release",
          "pool_size": 1092,
          "public": true,
          "added": "2012-11-23T10:55:12.776706"
        }
    """
    return {'uri':                    url_for('.samples_get', sample=instance.id),
            'user_uri':               url_for('.users_get', user=instance.user.id),
            'name':                   instance.name,
            'pool_size':              instance.pool_size,
            'public':                 instance.public,
            'added':                  str(instance.added.isoformat())}


@serializes(ActivationFailure)
@serializes(InvalidDataSource)
@serializes(TaskError)
def serialize_exception(instance):
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
def serialize_validation_error(instance):
    """
    A validation error is represented like other exceptions, but with the
    error code fixed as ``bad_request``.
    """
    return {'code':    'bad_request',
            'message': instance.message}


def serialize(instance, embed=None):
    """
    Create a RESTfull representation of an object as dictionary.

    This function dispatches to a specific serializer function depending on
    the type of object at hand.

    .. note:: Returns ``None`` if no serializer was found.
    .. note:: I don't think this construction of creating serializations is
        especially elegant, but it gets the job done and I really don't want
        any functionality for representations in the models themselves.
    .. todo:: Document `expand` keyword argument (and move to this decorator).
    .. todo:: Perhaps use `embed` instead of `expand`.
    """
    embed = embed or []
    for model, serializer in _serializers:
        if isinstance(instance, model):
            serialization = serializer(instance)
            serialization.update({field: serialize(getattr(instance, field))
                                  for field in embed})
            return serialization
