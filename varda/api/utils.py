"""
Various REST API utilities.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from functools import wraps
import urlparse

from flask import abort, request
from werkzeug.datastructures import Range
from werkzeug.exceptions import HTTPException
from werkzeug.http import parse_range_header

from ..models import Annotation, Coverage, DataSource, Sample, User, Variation
from .errors import ValidationError


def collection(rule):
    """
    Decorator for rules returning collections.

    The decorated view function recieves `begin` and `count` keyword
    arguments (so make sure these don't clash with any of the existing view
    function arguments).

    The view function should return a tuple of the total number of items in
    the collection and a response object.

    Example::

        >>> @api.route('/samples', methods=['GET'])
        >>> @collection
        >>> def samples_list(begin, count):
        ...     samples = Samples.query
        ...     return (samples.count(),
                        jsonify(samples=[serialize(s) for s in
                                         samples.limit(count).offset(begin)]))
    """
    # Todo: Should we return with status 206? But that's only allowed if the
    #     request included a Range header. Maybe we could return 406 if there
    #     was no Range header?
    @wraps(rule)
    def collection_rule(*args, **kwargs):
        r = parse_range_header(request.headers.get('Range')) \
            or Range('items', [(0, 20)])
        if r.units != 'items' or len(r.ranges) != 1:
            raise ValidationError('Invalid range')
        begin, end = r.ranges[0]
        if not 0 <= begin < end or end - begin > 500:
            raise ValidationError('Invalid range')
        kwargs.update(begin=begin, count=end - begin)
        total, response = rule(*args, **kwargs)
        if begin > max(total - 1, 0):
            abort(404)
        end = min(end, total)
        # Todo: Use ContentRange object from Werkzeug to construct this value.
        response.headers.add('Content-Range',
                             'items %d-%d/%d' % (begin, end - 1, total))
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


def user_by_uri(app, uri):
    """
    Get a user from its URI.
    """
    try:
        args = parse_args(app, 'api.user_get', uri)
    except ValueError:
        return None
    return User.query.get(args['user'])


def sample_by_uri(app, uri):
    """
    Get a sample from its URI.
    """
    try:
        args = parse_args(app, 'api.sample_get', uri)
    except ValueError:
        return None
    return Sample.query.get(args['sample'])


def variation_by_uri(app, uri):
    """
    Get a variation from its URI.
    """
    try:
        args = parse_args(app, 'api.variation_get', uri)
    except ValueError:
        return None
    return Variation.query.get(args['variation'])


def coverage_by_uri(app, uri):
    """
    Get a coverage from its URI.
    """
    try:
        args = parse_args(app, 'api.coverage_get', uri)
    except ValueError:
        return None
    return Coverage.query.get(args['coverage'])


def data_source_by_uri(app, uri):
    """
    Get a data source from its URI.
    """
    try:
        args = parse_args(app, 'api.data_source_get', uri)
    except ValueError:
        return None
    return DataSource.query.get(args['data_source'])


def annotation_by_uri(app, uri):
    """
    Get an annotation from its URI.
    """
    try:
        args = parse_args(app, 'api.annotation_get', uri)
    except ValueError:
        return None
    return Annotation.query.get(args['annotation'])


def user_by_login(login, password):
    """
    Check if login and password are correct and return the user if so, else
    return ``None``.
    """
    user = User.query.filter_by(login=login).first()
    if user is not None and user.check_password(password):
        return user
