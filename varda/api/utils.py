"""
Various REST API utilities.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from functools import wraps
import re
import urlparse

from cerberus import ValidationError as CerberusValidationError, Validator
from flask import request
from werkzeug.exceptions import HTTPException

from .errors import ValidationError


class ApiValidator(Validator):
    def _validate_required_fields(self):
        # This is a bit of a hack, we modify the schema to set the `required`
        # `rule` for each field if it is not set to ``False``.
        for definition in self.schema.values():
            definition['required'] = definition.get('required', True)
        super(ApiValidator, self)._validate_required_fields()

    def _validate_allowed(self, allowed_values, field, value):
        # This is also a bit of a hack, we add a special case for the
        # `allowed` rule on string values.
        if isinstance(value, basestring):
            if value not in allowed_values:
                self._error("unallowed value '%s' for field '%s'"
                            % (value, field))
        else:
            super(ApiValidator, self)._validate_allowed(allowed_values,
                                                        field, value)

    def _validate_schema(self, schema, field, value):
        # And another hack, we add a special case for the `schema` rule on
        # list values.
        if isinstance(value, list):
            for v in value:
                validator = self.__class__({field: schema})
                if not validator.validate({field: v}):
                    self._error(validator.errors)
        else:
            super(V, self)._validate_schema(schema, field, value)

    def _validate_safe(self, safe, field, value):
        expression = '[a-zA-Z][a-zA-Z0-9._-]*$'
        if safe and not re.match(expression, value):
            self._error("value for field '%s' must match the expression '%s'"
                        % (field, expression))


def validate(schema):
    """
    Decorator for request payload validation.

    :arg schema: Schema as used by `Cerberus <http://cerberus.readthedocs.org/>`_.
    :type schema: dict

    All defined fields in the schema are required by default.

    The decorated view function recieves validated data as keyword argument
    `data` as well as all of its original arguments.

    Example::

        >>> @api.route('/users/<int:user_id>/samples', methods=['POST'])
        >>> @validate({'name': {'type': 'string'}})
        >>> def add_sample(data, user_id):
        ...    user = User.query.get(user_id)
        ...    sample = Sample(user, data['name'])
    """
    validator = ApiValidator(schema)
    def validate_with_schema(rule):
        @wraps(rule)
        def validating_rule(*args, **kwargs):
            # Todo: For nested data structures, we only want to accept a
            #     proper datatype such as JSON. If we accept HTTP form data,
            #     we should somehow decode all values from strings.
            data = request.json or request.form
            try:
                if not validator.validate(data):
                    raise ValidationError('Invalid request content: %s'
                                          % '; '.join(validator.errors))
            except CerberusValidationError as e:
                raise ValidationError('Invalid request content: %s' % str(e))
            kwargs.update(data=data)
            return rule(*args, **kwargs)
        return validating_rule
    return validate_with_schema


def optional_kwargs(decorator):
    @wraps(decorator)
    def decorator_with_optional_kwargs(*args, **kwargs):
        if len(args) == 1 and not kwargs and callable(args[0]):
            return decorator()(args[0])
        return decorator(*args, **kwargs)
    return decorator_with_optional_kwargs


@optional_kwargs
def collection(**fields):
    """
    Decorator for rules returning collections, adding ranges and filters.

    .. todo:: Correct documentation, we now use kwargs. Also not the order of
        the decorators to play nice with eachother (collection before ensure).

    The decorated view function recieves `first`, `count` and `filters`
    arguments, any arguments from the parsed route URL come after that. The
    view function should return a tuple of the total number of items in the
    collection and a response object.

    Example::

        >>> @api.route('/samples', methods=['GET'])
        >>> @collection
        >>> def samples_list(first, count):
        ...     samples = Samples.query
        ...     return (samples.count(),
                        jsonify(samples=[serialize(s) for s in
                                         samples.limit(count).offset(first)]))

    .. todo:: Example with filters.
    """
    def filtered_collection(rule):
        @wraps(rule)
        def collection_rule(*args, **kwargs):
            filters = {}
            for field, field_type in fields.items():
                if field not in request.args:
                    continue
                if field_type == 'bool':
                    if request.args[field] not in ('true', 'false'):
                        raise ValidationError('Invalid filter on "%s"' % field)
                    filters[field] = request.args[field] == 'true'
                elif field_type == 'string':
                    filters[field] = request.args[field]

            # Todo: Use `parse_range_header` from Werkzeug:
            #     http://werkzeug.pocoo.org/docs/http/#werkzeug.http.parse_range_header
            range_header = request.headers.get('Range', 'items=0-19')
            if not range_header.startswith('items='):
                raise ValidationError('Invalid range')
            try:
                first, last = (int(i) for i in range_header[6:].split('-'))
            except ValueError:
                raise ValidationError('Invalid range')
            if not 0 <= first <= last or last - first + 1 > 500:
                raise ValidationError('Invalid range')
            kwargs.update(first=first, count=last - first + 1, filters=filters)
            total, response = rule(*args, **kwargs)
            if first > max(total - 1, 0):
                abort(404)
            last = min(last, total - 1)
            response.headers.add('Content-Range',
                                 'items %d-%d/%d' % (first, last, total))
            return response
        return collection_rule

    return filtered_collection


def parse_args(app, view, uri):
    """
    Parse view arguments from given URI.
    """
    if not uri:
        raise ValueError('no uri to resolve')
    path = urlparse.urlsplit(uri).path
    try:
        endpoint, args = app.url_map.bind('').match(path)
        assert app.view_functions[endpoint] is view
    except (AssertionError, HTTPException):
        raise ValueError('uri "%s" does not resolve to view "%s"'
                         % (uri, view.__name__))
    return args
