#!/usr/bin/env python
"""
Run the Varda REST server.

To reset the database:

    from varda import db
    db.drop_all()
    db.create_all()

"""


from varda import app


app.run(debug=True)
