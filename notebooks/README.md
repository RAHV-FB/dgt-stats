# Notebooks

Notebooks are numbered in the order a reviewer should run or read them:

```text
00_source_audit.ipynb          reproduces docs/data_inventory.md
01_validation.ipynb            reconciliation and missingness profile
02_trends.ipynb                Q1
03_time_patterns.ipynb         Q2
04_severity_model.ipynb        Q3 (scripts/model.py writes the tables)
05_geography_rates.ipynb       Q4
06_road_users.ipynb            Q5
07_older_drivers.ipynb         Q7 (denominator ladder)
08_heavy_vehicles_2022.ipynb   Q6
09_policy_its.ipynb            Q8
10_speed_context.ipynb         Q9
```

None exist yet: the pipeline is script-driven (`scripts/`), and notebooks will be added as explanatory
companions once the corresponding results are on the site.

Notebook outputs should be reproducible from a clean environment. Reusable transformations, metrics, models and plotting functions belong in `src/dgt_stats/`; notebooks should focus on analysis and explanation.
