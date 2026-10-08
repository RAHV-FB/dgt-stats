"""EMEF, the working-day mobility survey of the ATM of the Barcelona area, 2014–2024.

The public-use microdata have one respondent file and one trip file a year (``data/raw/emef``).
:mod:`variables` records, year by year, which column holds each harmonised variable and what its
codes mean, read from that year's own dictionary; :mod:`ingest` reads the files, harmonises them
and checks them against the published survey universe; :mod:`distance` converts the banded
straight-line trip distance into road kilometres; :mod:`exposure` estimates car driving by age,
sex, area and year with the survey weights and replicate-free standard errors.
"""
