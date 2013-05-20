"""
Various REST API utilities.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from functools import wraps
import urlparse

from flask import abort, request
from werkzeug.datastructures import ContentRange
from werkzeug.exceptions import HTTPException
from werkzeug.http import parse_range_header

from ..models import (Annotation, Coverage, DataSource, Sample, Token, User,
                      Variation)
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
    # To avoid unlimited response sizes we wouldn't like to respond with the
    # entire collection if the request didn't include a Range header. There
    # are two obvious solutions:
    #
    # - Act as if some default Range header value was included.
    # - Return 400 Range Required.
    #
    # The first option violates HTTP since 206 is only allowed if the request
    # included a Range header. The second option disables easy browsing of
    # collections with a standard web browser.
    #
    # We choose the second option (but aren't too happy with it). See [1] for
    # more discussion on this.
    #
    # [1] http://stackoverflow.com/questions/924472/paging-in-a-rest-collection
    @wraps(rule)
    def collection_rule(*args, **kwargs):
        # Note: As an alternative, we could use the following instead of a
        #     missing Range header: `Range('items', [(0, 500)])`.
        try:
            r = parse_range_header(request.headers['Range'])
        except KeyError:
            raise ValidationError('Range required')
        if r is None or r.units != 'items' or len(r.ranges) != 1:
            abort(416)
        begin, end = r.ranges[0]
        if not 0 <= begin < end:
            abort(416)
        end = min(end, begin + 500)
        kwargs.update(begin=begin, count=end - begin)
        total, response = rule(*args, **kwargs)
        if begin > total - 1:
            response.headers.add('Content-Range',
                                 ContentRange('items', None, None, total))
            abort(416)
        end = min(end, total)
        response.headers.add('Content-Range',
                             ContentRange('items', begin, end, total))
        return response, 206
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


def token_by_uri(app, uri):
    """
    Get a token from its URI.
    """
    try:
        args = parse_args(app, 'api.token_get', uri)
    except ValueError:
        return None
    return Token.query.get(args['token'])


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


def user_by_token(token):
    """
    Check if token belongs to a user and return the user if so, else return
    ``None``.
    """
    return User.query.join(Token).filter_by(key=token).first()
