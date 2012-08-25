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
