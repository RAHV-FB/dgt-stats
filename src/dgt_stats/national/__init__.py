"""Spain: national statistics from DGT, INE, the Ministerio de Transportes and CORES.

Sources: DGT crash microdata (one row per crash with victims, 2016–2024), the DGT yearbook series
(1993–2024) and statistical tables (2014–2024), the DGT driver census and kilometre estimates, the
DGT speed-factor report, INE resident population, CORES road fuel, toll-motorway traffic and the
Ministry's interurban vehicle-kilometres. None of them carries a person record.

Readers, in pipeline order:

``io_microdata``  the yearly crash workbooks to one harmonised staging table
``io_tables``     the yearbook series and statistical tables
``io_exposure``   the driver census and the kilometre estimates
``io_population`` INE residents by province, age and sex
``io_reports``    the speed-factor report's annex tables
``io_traffic``    road fuel, toll-motorway traffic and measured interurban kilometres
``codes``, ``labels``, ``derive``  code lists, English labels and derived crash fields
``reconcile``     the 482 checks that tie the staging layer to DGT's published totals

Analyses, each writing result tables through :mod:`summaries` (``scripts/run.py national``):

``risk_trends``   counts against exposure, 2019–2024 and the long run since 1993
``seasonality``   deaths by month beside monthly traffic
``road_class``    casualties by road class and deaths per measured interurban kilometre
``vehicles``      vehicles in crashes per vehicle and per kilometre
``speed``, ``factors``  recorded speed status and the other police-recorded factors
``policy``        the 2006 points-licence case study (supporting analysis)
``features``, ``associations``  associations in DGT crash records (supporting, not predictive)
``crash_cells``   the crash explorer's counts
``forecast``      the withdrawn monthly deaths forecast, kept as a record
``model_cards``   the cards of the two national models
"""
