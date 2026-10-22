# Scripts

One command builds the project: `scripts/run.py`. It runs the stages declared in
`src/dgt_stats/pipeline.py`, each in its own process and in the order their inputs require.

```bash
python scripts/run.py --list               # every stage, in order, with what it does and writes
python scripts/run.py all                  # everything
python scripts/run.py <section>            # one section: national, regional, drivers, models,
                                           # sources, charts or site
python scripts/run.py <section>.<stage>    # one stage, e.g. national.ingest or models.calculator
python scripts/run.py regional.build models.features   # several, in the order given
```

Options: `--force` rebuilds the data layers that already exist (`national.ingest`,
`national.process`, `regional.build`); `--years Y ...` limits `national.ingest` to some years of
the crash microdata; `-v` logs at debug level. A failed stage stops the run, and
`national.reconcile` fails if any of the 482 reconciliation checks does not pass.

The stages, in the order `all` runs them:

| Section | Stages |
|---|---|
| national | `ingest` → `reconcile` → `process` → `associations` → `results` (and `cards`, after the models) |
| regional | `build` → `quality` → `analyse` |
| drivers | `tables` → `emef` → `exposure` |
| models | `features` → `fit` → `validate` → `calculator` → `review` |
| sources | `inventory` → `profile` (and `catalogue`, last of all) |
| charts | `figures` |
| site | `build` |

Run by name only: `national.withdrawn` (the withdrawn forecast's tables, slow),
`regional.organise` (file loose regional downloads under `data/raw/<source>/`) and
`models.documents` (re-render the validation documents from saved tables).

Scripts are thin: the logic of each stage is in its section's `stages.py` under `src/dgt_stats/`
and is covered by tests.

## Tools outside the build (`tools/`)

- `fetch_ine.py [--table provinces|single_age] [--from-file CSV]`: rebuilds the committed INE
  population extracts (`data/raw/ine/ine_poblacion_provincias_edad_sexo.csv` from table 56947,
  `data/raw/ine/ine_poblacion_edad_simple_sexo.csv` from table 56934), or filters an already
  downloaded copy;
- `fetch_edm.py [--from-dir DIR]`: rebuilds the committed extracts of the Madrid household travel
  survey 2018 (`data/raw/crtm/edm2018/`) from the CRTM's workbooks;
- `build_fonts.py <source font directory>`: cuts the committed font subsets (the site's web fonts
  and the charts' serif) from the open fonts in the google/fonts repository; needed only to change
  the character set or update a font.
