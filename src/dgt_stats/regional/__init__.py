"""The regional crash records: Catalonia's crashes with a death or serious injury and Barcelona's.

The national DGT records (:mod:`dgt_stats.national`) have one row per crash and no person records.
This section adds two sources that do carry observation units the national data lack:

* Catalonia (Servei Català de Trànsit export): one row per crash with at least one death or
  serious injury, 2010–2023. No source identifier; the row is the unit.
* Barcelona (Guàrdia Urbana, Open Data BCN): six tables for 2025 that share the crash identifier
  ``Numero_expedient``: crashes, accident types, people, vehicle records, mediate causes and
  driver-cause records.

Modules, in pipeline order:

``files``       find the raw files by their columns, de-duplicate them by SHA-256, read them as text
``barcelona``   staging and canonical Barcelona tables, cause aggregation, the cardinality checks
``catalonia``   staging and canonical Catalonia table
``coordinates`` the UTM/WGS84 audit of the Barcelona coordinates
``vehicles``    the audit of the Barcelona vehicle-record table (quarantined for unique-vehicle use)
``quality``     the data-quality report
``descriptive`` transparent rates with their N behind every model
``crosssource`` the aggregate-level comparisons with the DGT and INE data that a real key allows
``common``      provenance-stamped Parquet, slugs and intervals, shared with :mod:`dgt_stats.models`

The models fitted to these records are in :mod:`dgt_stats.models`, their figures in
:mod:`dgt_stats.charts.regional`. The rule every module follows: an observation, a key or a
variable must exist in the rows of a file under ``data/raw``. Nothing is imputed from outside
studies, and the two regional sources are never joined to each other or to the DGT microdata at
the crash level.
"""
