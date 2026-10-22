"""Drivers by age and sex: crashes per licence holder and per kilometre driven.

No national source measures how far drivers of each age drive. This section puts kilometres on
driver ages from travel surveys and divides DGT's counts of car drivers involved in crashes by
them. Sources: DGT driver tables, driver census and kilometre estimates (shared with
:mod:`dgt_stats.national`); INE population by single year of age; the EMEF working-day survey of
the Barcelona area (2014–2024); the Madrid household travel survey EDM2018; MOVILIA 2006–2007;
Idescat's 2024 census release; and figures typed from documents that are not archived (the
EMEF 2021 distance report and the Fundació RACC 2013 survey, and the EMEF technical document's
yearly totals, which only check the respondent files).

``driver_risk``    rates per licence holder and per kilometre by owner age, from DGT's tables
``emef``           the EMEF microdata: ingestion, distances and car-driving exposure by age
``edm2018``        the Madrid survey's car driving by exact age
``exposure_risk``  car drivers involved per kilometre by age, nationally and in Barcelona city
"""
