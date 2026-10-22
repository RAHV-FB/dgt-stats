"""Road safety in Spain: a reproducible statistical study built only from published data.

The package is split into the same sections as the data, the result tables, the documents and the
site, so that every result can be traced to the sources it comes from (:mod:`dgt_stats.catalogue`
is the map):

``national``  Spain: DGT, INE, Ministerio de Transportes and CORES statistics
``drivers``   drivers by age and sex: DGT driver tables and census, and the travel surveys
              (EMEF, EDM2018, MOVILIA) that put kilometres on driver ages
``regional``  the Catalan (Servei Català de Trànsit) and Barcelona (Guàrdia Urbana) crash records
``models``    the crash-severity models trained on those records and their cross-source tests
``sources``   cross-cutting: the inventory of every raw file and how each source came to exist

``charts`` draws the figures and ``site`` writes the static site, both from the committed result
tables only. ``paths``, ``rates``, ``agebands`` and ``regions`` are shared helpers.
"""

__version__ = "1.0.0"
