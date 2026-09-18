# Notebooks

Notebooks are numbered in the order a reviewer should run or read them:

```text
00_source_audit.ipynb
01_data_quality.ipynb
02_crash_trends.ipynb
03_exposure_adjusted_rates.ipynb
04_factors_and_interactions.ipynb
05_speed_and_road_design.ipynb
06_heavy_vehicles_and_buses.ipynb
07_campaign_evaluation.ipynb
08_final_story.ipynb
```

Notebook outputs should be reproducible from a clean environment. Reusable transformations, metrics, models and plotting functions belong in `src/dgt_stats/`; notebooks should focus on analysis and explanation.
