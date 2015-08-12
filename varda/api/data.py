"""
Utilities for working with request data.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from copy import deepcopy
from functools import wraps
import re
import urllib

from cerberus import ValidationError as CerberusValidationError, Validator
import cerberus.errors
from flask import abort, current_app, g, request

from ..models import (Annotation, Coverage, DataSource, Group, Sample, Token,
                      User, Variation)
from .errors import ValidationError
from .utils import (annotation_by_uri, coverage_by_uri, data_source_by_uri,
                    group_by_uri, sample_by_uri, token_by_uri, user_by_uri,
                    variation_by_uri)


# Todo: Rename cast to coerce.
def cast(document, schema):
    """
    Cast certain values in a data document to specific types.

    This enables us to transparently handle incoming values from a JSON parser
    as well as from URL query strings and HTTP request bodies, where every
    value is, well, a string.

    In addition, we use it to instantiate models from resource URIs, such that
    we can work with model instances directly in the API view functions.

    The function is 'silent', in the way that it will try to cast values but
    never complains on failure. Instead, it will just return the original
    value. The idea being that the reason for failure will be dealt with
    during validation.

    :arg document: Arbitrarily nested dictionary-like object containing our
        values.
    :type document: dict
    :arg schema: Cerberus validation schema.
    :type schema: dict

    :return: Copy of `document` with possible updated values that could be
        cast. Note that `document` is not modified in any way, but sub-
        structures may have been copied by reference in the return value.
    :rtype: dict
    """
    casters = {'list':            _cast_list,
               'dict':            _cast_dict,
               'integer':         _cast_integer,
               'boolean':         _cast_boolean,
               'directed_string': _cast_directed_string,
               'annotation':      _cast_annotation,
               'coverage':        _cast_coverage,
               'data_source':     _cast_data_source,
               'sample':          _cast_sample,
               'group':           _cast_group,
               'token':           _cast_token,
               'user':            _cast_user,
               'variant':         _cast_variant,
               'variation':       _cast_variation}
    return_document = {}
    for field, value in document.items():
        definition = schema.get(field)
        if definition and isinstance(definition, dict):
            caster = casters.get(definition.get('type'))
            if caster:
                return_document[field] = caster(value, definition)
            else:
                return_document[field] = value
    return return_document


def _cast_list(values, definition):
    if isinstance(values, basestring):
        if values:
            values = values.split(',')
        else:
            values = []
    if isinstance(values, list):
        schema = definition.get('schema')
        if schema and isinstance(schema, dict):
            return [cast({'key': value}, {'key': schema})['key']
                    for value in values]
        items = definition.get('items')
        if items and isinstance(items, list) and len(items) == len(values):
            return [cast({'key': value}, {'key': item})['key']
                    for value, item in zip(values, items)]
    return values


def _cast_dict(values, definition):
    if isinstance(values, basestring):
        if values:
            try:
                values = dict(value.split(':') for value in values.split(','))
            except ValueError:
                pass
        else:
            values = {}
    if isinstance(values, dict):
        schema = definition.get('schema')
        if schema and isinstance(schema, dict):
            return cast(values, schema)
    return values


def _cast_integer(value, definition):
    if isinstance(value, basestring):
        try:
            return int(value)
        except ValueError:
            pass
    return value


def _cast_boolean(value, definition):
    if isinstance(value, basestring):
        if value.lower() in ('true', 'yes', 'on', '1'):
            return True
        elif value.lower() in ('false', 'no', 'off', '0'):
            return False
    return value


def _cast_directed_string(value, definition):
    if isinstance(value, basestring):
        if value.startswith('-'):
            return value[1:], 'desc'
        if value.startswith('+'):
            return value[1:], 'asc'
        return value, 'asc'
    return value


# Todo: We'd like to get rid of the `current_app`. Unfortunately, it's also
#     not really attractive to pass the app as extra argument to all cast
#     functions.
def _cast_annotation(value, definition):
    if isinstance(value, int):
        return Annotation.query.get(value)
    elif isinstance(value, basestring):
        return annotation_by_uri(current_app, value)
    return value


def _cast_coverage(value, definition):
    if isinstance(value, int):
        return Coverage.query.get(value)
    elif isinstance(value, basestring):
        return coverage_by_uri(current_app, value)
    return value


def _cast_data_source(value, definition):
    if isinstance(value, int):
        return DataSource.query.get(value)
    elif isinstance(value, basestring):
        return data_source_by_uri(current_app, value)
    return value


def _cast_sample(value, definition):
    if isinstance(value, int):
        return Sample.query.get(value)
    elif isinstance(value, basestring):
        return sample_by_uri(current_app, value)
    return value


def _cast_group(value, definition):
    if isinstance(value, int):
        return Group.query.get(value)
    elif isinstance(value, basestring):
        return group_by_uri(current_app, value)
    return value


def _cast_token(value, definition):
    if isinstance(value, int):
        return Token.query.get(value)
    elif isinstance(value, basestring):
        return token_by_uri(current_app, value)
    return value


def _cast_user(value, definition):
    if isinstance(value, int):
        return User.query.get(value)
    elif isinstance(value, basestring):
        return user_by_uri(current_app, value)
    return value


def _cast_variant(value, definition):
    if isinstance(value, basestring) and len(value) <= 500:
        # Todo: I'm not so sure about the urllib.unquote call. I would've
        #     hoped that Werkzeug routing would unquote any argument in our
        #     url (e.g. '/variants/<str:variant>' in views.variant_get.
        match = re.match('([^:]+):([0-9]+)([a-zA-Z]{,200})>([a-zA-Z]{,200}$)',
                         urllib.unquote(value))
        try:
            chromosome, position, reference, observed = match.groups()
            return chromosome, int(position), reference, observed
        except AttributeError:
            pass
    return value


def _cast_variation(value, definition):
    if isinstance(value, int):
        return Variation.query.get(value)
    elif isinstance(value, basestring):
        return variation_by_uri(current_app, value)
    return value


# Todo: Instead of the light-weight Cerberus, I'm tempted to use the
#     `Colander <https://github.com/Pylons/colander>` library. My main problem
#     with it is that schema definitions are very verbose, not suitable as
#     arguments in our @data decorator. Some wrapper code generating Colander
#     schemas would be possible though.
#     See https://github.com/ccnmtl/mvsim/blob/master/main/models.py
#     Other alternatives would be the `Voluptuous <https://github.com/alecthomas/voluptuous>`
#     or `schema <https://github.com/halst/schema>` libraries.
class ApiValidator(Validator):
    def _validate(self, *args, **kwargs):
        self.missing_id = False
        return super(ApiValidator, self)._validate(*args, **kwargs)

    def _validate_safe(self, safe, field, value):
        expression = '[a-zA-Z][a-zA-Z0-9._-]*$'
        if safe and not re.match(expression, value):
            self._error("value for field '%s' must match the expression '%s'"
                        % (field, expression))

    def _validate_id(self, id_, field, value):
        if id_ and not value:
            self.missing_id = True

    def _validate_type_directed_string(self, field, value):
        if not (isinstance(value, tuple) or
                len(value) == 2 or
                isinstance(value[0], basestring)
                or value[1] in ('asc', 'desc')):
            self._error(cerberus.errors.ERROR_BAD_TYPE % (field, 'directed string'))

    def _validate_type_annotation(self, field, value):
        if not isinstance(self.document[field], Annotation):
            self._error(cerberus.errors.ERROR_BAD_TYPE % (field, 'annotation'))

    def _validate_type_coverage(self, field, value):
        if not isinstance(self.document[field], Coverage):
            self._error(cerberus.errors.ERROR_BAD_TYPE % (field, 'coverage'))

    def _validate_type_data_source(self, field, value):
        if not isinstance(self.document[field], DataSource):
            self._error(cerberus.errors.ERROR_BAD_TYPE % (field, 'data_source'))

    def _validate_type_sample(self, field, value):
        if not isinstance(self.document[field], Sample):
            self._error(cerberus.errors.ERROR_BAD_TYPE % (field, 'sample'))

    def _validate_type_group(self, field, value):
        if not isinstance(self.document[field], Group):
            self._error(cerberus.errors.ERROR_BAD_TYPE % (field, 'group'))

    def _validate_type_token(self, field, value):
        if not isinstance(self.document[field], Token):
            self._error(cerberus.errors.ERROR_BAD_TYPE % (field, 'token'))

    def _validate_type_user(self, field, value):
        if not isinstance(self.document[field], User):
            self._error(cerberus.errors.ERROR_BAD_TYPE % (field, 'user'))

    def _validate_type_variant(self, field, value):
        if isinstance(value, tuple):
            try:
                chromosome, position, reference, observed = value
                if (all(isinstance(x, basestring)
                        for x in (chromosome, reference, observed))
                    and isinstance(position, int)):
                    # Todo: Must we check here if we're dealing with DNA?
                    #     Also, these length checks are quire arbitrary.
                    if (len(chromosome) < 100 and
                        len(reference) < 300 and
                        len(observed) < 300):
                        return
            except ValueError:
                pass
        self._error(cerberus.errors.ERROR_BAD_TYPE % (field, 'variant'))

    def _validate_type_variation(self, field, value):
        if not isinstance(self.document[field], Variation):
            self._error(cerberus.errors.ERROR_BAD_TYPE % (field, 'variation'))


def data(**schema):
    """
    Decorator for request payload parsing and validation.

    :arg schema: Schema as used by `Cerberus <http://cerberus.readthedocs.org/>`_.
    :type schema: dict

    Request payload is either read from a json-encoded request body, or from a
    combination of the request body encoded as form data and query string
    parameters.

    The decorated view function recieves validated data as keyword argument
    `data` as well as all of its original arguments.

    Example::

        >>> @api.route('/users/<int:user_id>/samples', methods=['POST'])
        >>> @data(name={'type': 'string', 'id': True})
        >>> def add_sample(data, user_id):
        ...     user = User.query.get(user_id)
        ...     sample = Sample(user, data['name'])
    """
    validator = ApiValidator(schema)
    def data_with_validator(rule):
        @wraps(rule)
        def data_rule(*args, **kwargs):
            # Todo: Look into Flask's `request.on_json_loading_failed`.
            raw_data = request.json or request.values.to_dict()
            raw_data.update(**kwargs)
            data = cast(raw_data, schema)
            try:
                if not validator.validate(data):
                    if validator.missing_id:
                        abort(404)
                    raise ValidationError('Invalid request content: %s'
                                          % '; '.join(validator.errors))
            except CerberusValidationError as e:
                raise ValidationError('Invalid request content: %s' % str(e))
            return rule(*args, **validator.document)
        return data_rule
    return data_with_validator
