"""The crash-level microdata layer: Catalonia's serious and fatal crashes and Barcelona's 2025 records.

The national DGT layer (``dgt_stats.io_*``) reads published workbooks and one-row-per-crash
microdata with no person records. This package adds two sources that do carry real observation
units the project did not have:

* Catalonia (Servei Català de Trànsit export): one row per crash with at least one death or
  serious injury, 2010 onwards. No source identifier; the row is the unit.
* Barcelona (Guàrdia Urbana, Open Data BCN): six tables for 2025 that share the crash identifier
  ``Numero_expedient``: crashes, accident types, people, vehicle records, mediate causes and
  driver-cause records.

Modules, in pipeline order:

``sources``     the raw files and how they are read as text
``barcelona``   staging and canonical Barcelona tables, cause aggregation, the cardinality checks
``catalonia``   staging and canonical Catalonia table
``quality``     the structure and consistency checks of the two regional files
``ml``          the Catalan feature table (``ml.features``) and the recording check on its
                placeholder fields (``ml.recording``)
``descriptive`` transparent rates with their N
``crosssource`` the aggregate-level comparisons with the DGT and INE layers that a real key allows
``charts``      the figures of the regional pages

The rule every module follows: an observation, a key or a variable must exist in the rows of a
file under ``data/raw``. Nothing is imputed from outside studies, and the two regional sources are
never joined to each other or to the DGT microdata at the crash level.
"""
