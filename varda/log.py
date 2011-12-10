"""
Logging.

Note: This is a temporary implementation doing nothing much. A real
    implementation is on celly but not committed yet.
"""


from varda import app


debug = app.logger.debug
info = app.logger.info
warning = app.logger.warning
error = app.logger.error
