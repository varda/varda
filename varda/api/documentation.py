# -*- coding: utf-8 -*-
"""
REST API documentation.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from flask import Blueprint, current_app


docs = Blueprint('docs', 'docs')


@docs.route('/')
def root_get():
    """
    Varda server API documentation.
    """
    s = '<html><h1>Hi!</h1><ul>'
    for rule in current_app.url_map.iter_rules():
        s += '<li>'
        s += '<code>' + rule.rule + '/'.join(rule.arguments) + '</code>'
        s += ' (' + ', '.join(rule.methods) + ')'
        s += '<pre>' + (current_app.view_functions[rule.endpoint].__doc__ or '') + '</pre>'
        s += '</li>'
    s += '</ul></html>'
    return s
