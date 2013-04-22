"""
API custom exceptions.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


class ActivationFailure(Exception):
    """
    Exception thrown on failure of sample activation.
    """
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super(ActivationFailure, self).__init__(code, message)


class AcceptError(Exception):
    """
    Exception thrown on incompatiblity with acceptable response
    characteristics.
    """
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super(AcceptError, self).__init__(code, message)


class ValidationError(Exception):
    """
    Exception thrown on unsuccessful data validation.
    """
    def __init__(self, message):
        self.message = message
        super(ValidationError, self).__init__(message)
