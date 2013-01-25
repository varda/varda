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
from cerberus.errors import ERROR_BAD_TYPE
from flask import current_app, g, request

from ..models import Annotation, Coverage, DataSource, Sample, User, Variation
from .errors import ValidationError
from .utils import (annotation_by_uri, coverage_by_uri, data_source_by_uri,
                    sample_by_uri, user_by_uri, variation_by_uri)


# Todo: We currently hacked the Validator class a bit such that some type
#     casting is done in the 'type' rules by modifying the document in-place.
#     This isn't really how Cerberus works and there might be a better way of
#     doing things.
# Todo: I would like to have the app as extra argument to the constructor, so
#     that it can be given to the `*_by_uri` functions and they would no
#     longer need the ugly `current_app`. Unfortunately, that's not so easy
#     since `Validator` methods instantiate new objects which would miss the
#     argument.
# Todo: Instead of the light-weight Cerberus, I'm tempted to use the
#     `Colander <https://github.com/Pylons/colander>` library. My main problem
#     with it is that schema definitions are very verbose, not suitable as
#     arguments in our @data decorator. Some wrapper code generating Colander
#     schemas would be possible though.
#     See https://github.com/ccnmtl/mvsim/blob/master/main/models.py
class ApiValidator(Validator):
    # Todo: Try to get this in upstream Cerberus.
    def _validate_allowed(self, allowed_values, field, value):
        # This is a bit of a hack, we add a special case for the `allowed`
        # rule on string values.
        if isinstance(value, basestring):
            if value not in allowed_values:
                self._error("unallowed value '%s' for field '%s'"
                            % (value, field))
        else:
            super(ApiValidator, self)._validate_allowed(allowed_values,
                                                        field, value)

    # Todo: Try to get this in upstream Cerberus.
    def _validate_schema(self, schema, field, value):
        # And another hack, we add a special case for the `schema` rule on
        # list values.
        if isinstance(value, list):
            self.document[field] = []
            for v in value:
                validator = self.__class__({field: schema})
                if not validator.validate({field: v}):
                    self._error(validator.errors)
                self.document[field].append(validator.document[field])
        else:
            super(ApiValidator, self)._validate_schema(schema, field, value)

    def _validate_items_list(self, schemas, field, values):
        if len(schemas) != len(values):
            self._error(ERROR_ITEMS_LIST % (field, len(schemas)))
        else:
            self.document[field] = []
            for i in range(len(schemas)):
                key = "_data" + str(i)
                validator = self.__class__({key: schemas[i]})
                if not validator.validate({key: values[i]}):
                    self._error(["'%s': " % field + error
                                for error in validator.errors])
                self.document[field].append(validator.document[key])

    def _validate_safe(self, safe, field, value):
        expression = '[a-zA-Z][a-zA-Z0-9._-]*$'
        if safe and not re.match(expression, value):
            self._error("value for field '%s' must match the expression '%s'"
                        % (field, expression))

    def _validate_type_list(self, field, value):
        if isinstance(value, basestring):
            if value:
                self.document[field] = value.split(',')
            else:
                self.document[field] = []
        super(ApiValidator, self)._validate_type_list(field,
                                                      self.document[field])

    def _validate_type_integer(self, field, value):
        if isinstance(value, basestring):
            try:
                self.document[field] = int(value)
            except ValueError:
                pass
        super(ApiValidator, self)._validate_type_integer(field,
                                                         self.document[field])

    def _validate_type_boolean(self, field, value):
        if isinstance(value, basestring):
            if value.lower() in ('true', 'yes', 'on', '1'):
                self.document[field] = True
            elif value.lower() in ('false', 'no', 'off', '0'):
                self.document[field] = False
        super(ApiValidator, self)._validate_type_boolean(field,
                                                         self.document[field])

    def _validate_type_user(self, field, value):
        if isinstance(value, int):
            self.document[field] = User.query.get(value)
        elif isinstance(value, basestring):
            self.document[field] = user_by_uri(current_app, value)
        if not isinstance(self.document[field], User):
            self._error(ERROR_BAD_TYPE % (field, 'user'))

    def _validate_type_sample(self, field, value):
        if isinstance(value, int):
            self.document[field] = Sample.query.get(value)
        elif isinstance(value, basestring):
            self.document[field] = sample_by_uri(current_app, value)
        if not isinstance(self.document[field], Sample):
            self._error(ERROR_BAD_TYPE % (field, 'sample'))

    def _validate_type_variation(self, field, value):
        if isinstance(value, int):
            self.document[field] = Variation.query.get(value)
        elif isinstance(value, basestring):
            self.document[field] = variation_by_uri(current_app, value)
        if not isinstance(self.document[field], Variation):
            self._error(ERROR_BAD_TYPE % (field, 'variation'))

    def _validate_type_coverage(self, field, value):
        if isinstance(value, int):
            self.document[field] = Coverage.query.get(value)
        elif isinstance(value, basestring):
            self.document[field] = coverage_by_uri(current_app, value)
        if not isinstance(self.document[field], Coverage):
            self._error(ERROR_BAD_TYPE % (field, 'coverage'))

    def _validate_type_data_source(self, field, value):
        if isinstance(value, int):
            self.document[field] = DataSource.query.get(value)
        elif isinstance(value, basestring):
            self.document[field] = data_source_by_uri(current_app, value)
        if not isinstance(self.document[field], DataSource):
            self._error(ERROR_BAD_TYPE % (field, 'data_source'))

    def _validate_type_annotation(self, field, value):
        if isinstance(value, int):
            self.document[field] = Annotation.query.get(value)
        elif isinstance(value, basestring):
            self.document[field] = annotation_by_uri(current_app, value)
        if not isinstance(self.document[field], Annotation):
            self._error(ERROR_BAD_TYPE % (field, 'annotation'))

    def _validate_type_variant(self, field, value):
        if not isinstance(value, basestring):
            self._error(ERROR_BAD_TYPE % (field, 'variant'))
            return
        # Todo: I'm not so sure about the urllib.unquote call. I would've
        #     hoped that Werkzeug routing would unquote any argument in our
        #     url (e.g. '/variants/<str:variant>' in views.variant_get.
        match = re.match('([^:]+):([0-9]+)([a-zA-Z]{,200})>([a-zA-Z]{,200}$)',
                         urllib.unquote(value))
        try:
            chromosome, position, reference, observed = match.groups()
            self.document[field] = chromosome, int(position), reference, observed
        except AttributeError:
            raise Exception('hier: %s' % urllib.unquote(value))
            self._error(ERROR_BAD_TYPE % (field, 'variant'))


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
        >>> @data(name={'type': 'string'})
        >>> def add_sample(data, user_id):
        ...     user = User.query.get(user_id)
        ...     sample = Sample(user, data['name'])
    """
    validator = ApiValidator(schema)
    def data_with_validator(rule):
        @wraps(rule)
        def data_rule(*args, **kwargs):
            # Todo: Look into Flask's `request.on_json_loading_failed`.
            data = deepcopy(request.json) or request.values.to_dict()
            data.update(**kwargs)
            try:
                if not validator.validate(data):
                    raise ValidationError('Invalid request content: %s'
                                          % '; '.join(validator.errors))
            except CerberusValidationError as e:
                raise ValidationError('Invalid request content: %s' % str(e))
            return rule(*args, **validator.document)
        return data_rule
    return data_with_validator
