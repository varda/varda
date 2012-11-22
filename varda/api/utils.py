"""
Various REST API utilities.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


import urlparse

from werkzeug.exceptions import HTTPException


def parse_list(data):
    """
    Parse a list serialized as string into a Python list.
    """
    if isinstance(data, list):
        return data
    if not data:
        return []
    return [x.strip() for x in data.split(',')]


def parse_dict(data):
    """
    Parse a dictionary serialized as string into a Python dictionary.
    """
    if isinstance(data, dict):
        return data
    if not data:
        return {}
    return dict(x.strip().split('=') for x in data.split(','))


def parse_bool(data):
    """
    Parse a boolean serialized as string into a Python bool.
    """
    if isinstance(data, bool):
        return data
    return data.lower() in ('true', 'yes', 'on')


def parse_args(app, view, uri):
    """
    Parse view arguments from given uri.

    .. todo:: Support an application root to be stripped from the uri path.
    """
    path = urlparse.urlsplit(uri).path
    try:
        endpoint, args = app.url_map.bind('').match(path)
        assert app.view_functions[endpoint] is view
    except (AssertionError, HTTPException):
        raise ValueError('uri "%s" does not resolve to view "%s"'
                         % (uri, view.__name__))
    return args
