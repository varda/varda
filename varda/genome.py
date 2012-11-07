"""
Wrapper for ``pyfasta`` to load a genome after instantiation.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from pyfasta import Fasta


class Genome(Fasta):
    """
    Version of ``pyfasta.Fasta`` that is initialized after instantiation.

    After creating an instance, call the ``init`` method with arguments you
    would normally give the constructor.

    Checking if an instance has been initialized can be done by looking at its
    boolean value.

    .. todo:: Check if ``pyfasta.Fasta`` is thread-safe. It depends on the
        application server model (and Celery model) if we need it.
    """
    def __init__(self):
        self.index = {}

    def init(self, *args, **kwargs):
        super(Genome, self).__init__(*args, **kwargs)
