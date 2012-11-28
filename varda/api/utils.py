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

    The decorated view function recieves validated data as its first argument,
    any arguments from the parsed route URL come after that.

    Example::

        @api.route('/users/<int:user_id>/samples', methods=['POST'])
        @validate({'name': {'type': 'string'}})
        def add_sample(data, user_id):
            user = User.query.get(user_id)
            sample = Sample(user, data['name'])
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
            return rule(data, *args, **kwargs)
        return validating_rule
    return validate_with_schema


def parse_args(app, view, uri):
    """
    Parse view arguments from given URI.
    """
    path = urlparse.urlsplit(uri).path
    try:
        endpoint, args = app.url_map.bind('').match(path)
        assert app.view_functions[endpoint] is view
    except (AssertionError, HTTPException):
        raise ValueError('uri "%s" does not resolve to view "%s"'
                         % (uri, view.__name__))
    return args
