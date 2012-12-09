"""
Various REST API utilities.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from copy import deepcopy
from functools import wraps
import re
import urlparse

from cerberus import ValidationError as CerberusValidationError, Validator
from cerberus.errors import ERROR_BAD_TYPE
from flask import current_app, g, request
from werkzeug.exceptions import HTTPException

from ..models import DataSource, Sample, User
from .errors import ValidationError


# Todo: We currently hacked the Validator class a bit such that some type
#     casting is done in the 'type' rules by modifying the document in-place.
#     Perhaps it is a better (and safer) idea to reconstruct a validated
#     document from scratch, which would only contain fields that are
#     defined in the schema.
class ApiValidator(Validator):
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
            self.document[field] = []
            for v in value:
                validator = self.__class__({field: schema})
                if not validator.validate({field: v}):
                    self._error(validator.errors)
                self.document[field].append(validator.document[field])
        else:
            super(V, self)._validate_schema(schema, field, value)

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
        if isinstance(value, basestring):
            self.document[field] = user_by_uri(value)
        if not isinstance(self.document[field], User):
            self.error(ERROR_BAD_TYPE % (field, 'user'))

    def _validate_type_sample(self, field, value):
        if isinstance(value, basestring):
            self.document[field] = sample_by_uri(value)
        if not isinstance(self.document[field], Sample):
            self.error(ERROR_BAD_TYPE % (field, 'sample'))

    def _validate_type_data_source(self, field, value):
        if isinstance(value, basestring):
            self.document[field] = data_source_by_uri(value)
        if not isinstance(self.document[field], DataSource):
            self.error(ERROR_BAD_TYPE % (field, 'data_source'))


def data(**schema):
    """
    Decorator for request payload parsing and validation.

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
    def data_with_validator(rule):
        @wraps(rule)
        def data_rule(*args, **kwargs):
            # Todo: Look into Flask's `request.on_json_loading_failed`.
            data = deepcopy(request.json) or request.values.to_dict()
            try:
                if not validator.validate(data):
                    raise ValidationError('Invalid request content: %s'
                                          % '; '.join(validator.errors))
            except CerberusValidationError as e:
                raise ValidationError('Invalid request content: %s' % str(e))
            kwargs.update(data=validator.document)
            return rule(*args, **kwargs)
        return data_rule
    return data_with_validator


def collection(rule):
    """
    Decorator for rules returning collections.

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
    @wraps(rule)
    def collection_rule(*args, **kwargs):
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
        kwargs.update(first=first, count=last - first + 1)
        total, response = rule(*args, **kwargs)
        if first > max(total - 1, 0):
            abort(404)
        last = min(last, total - 1)
        response.headers.add('Content-Range',
                             'items %d-%d/%d' % (first, last, total))
        return response
    return collection_rule


def parse_args(app, endpoint, uri):
    """
    Parse view arguments from given URI.
    """
    if not uri:
        raise ValueError('no uri to resolve')
    path = urlparse.urlsplit(uri).path
    try:
        matched_endpoint, args = app.url_map.bind('').match(path)
        assert matched_endpoint == endpoint
    except (AssertionError, HTTPException):
        raise ValueError('uri "%s" does not resolve to endpoint "%s"'
                         % (uri, endpoint))
    return args


def data_source_by_uri(uri):
    """
    Get a data source from its URI.
    """
    try:
        args = parse_args(current_app, 'api.data_sources_get', uri)
    except ValueError:
        return None
    return DataSource.query.get(args['data_source_id'])


def sample_by_uri(uri):
    """
    Get a sample from its URI.
    """
    try:
        args = parse_args(current_app, 'api.samples_get', uri)
    except ValueError:
        return None
    return Sample.query.get(args['sample_id'])


def user_by_uri(uri):
    """
    Get a user from its URI.
    """
    try:
        args = parse_args(current_app, 'api.users_get', uri)
    except ValueError:
        return None
    return User.query.filter_by(login=args['login']).first()


def user_by_login(login, password):
    """
    Check if login and password are correct and return the user if so, else
    return ``None``.
    """
    user = User.query.filter_by(login=login).first()
    if user is not None and user.check_password(password):
        return user


def data_is_true(field):
    def condition(data, **_):
        return data.get(field)
    return condition


def data_is_user(field):
    def condition(data, **_):
        return g.user is not None and g.user is data.get(field)
    return condition
