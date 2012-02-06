"""
Logging functionality for Varda server.

Copyright (c) 2011-2012, Leiden University Medical Center <humgen@lumc.nl>
Copyright (c) 2011-2012, Martijn Vermaat <martijn@vermaat.name>

Licensed under the MIT license, see the LICENSE file.
"""


from flask import g, request

from varda import app


def make_logger(base):
    def logger(message, *args, **kwargs):
        header = ''
        if request.remote_addr is not None:
            header = '[ip: %s] ' % request.remote_addr
            if g.user is not None:
                header += '[user: %s] ' % g.user.login
        base(header + message, *args, **kwargs)
    return logger


debug = make_logger(app.logger.debug)
info = make_logger(app.logger.info)
warning = make_logger(app.logger.warning)
error = make_logger(app.logger.error)
