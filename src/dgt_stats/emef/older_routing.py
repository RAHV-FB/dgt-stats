"""Respondents aged 75 and over inside the EMEF's 65-and-over group, as far as the questionnaire's
routing reveals them.

The public files give one age group for everyone aged 65 and over. One question shows part of
the age within it: P1b ("did you work for pay last week, even for one hour?", variable ``V01B``)
is asked of everyone who is not in work, except those who answer P1a as retired, pensioner or
aged 75 and over (code 3) and are aged 75 or over; the questionnaires' filter reads "P1a=3 i
edat<75". The filter is read from archived sources for every year this module uses: the 2022 and
2023 questionnaires (``data/raw/emef/2022/emef_2022_questionnaire.pdf``,
``data/raw/emef/2023/emef_2023_questionnaire.pdf``) and the 2024 executive summary
(``data/raw/emef/2024/emef_2024_executive_summary.pdf``, page 90); the 2014-2016 questionnaires,
read for the validation in the documents, are archived beside their years. A respondent aged 65
or over, not in work, with ``V01B`` blank, is therefore a retiree aged 75 or over.

The flag finds only retirees: people aged 75 and over who report another situation are asked P1b
and are not found. The weighted share of flagged respondents in the 65-and-over group is
therefore a *lower limit* on the share aged 75 and over in the survey's 65-and-over sample. It is
used for one thing only: the bound on how far too few people aged 75 and over in that sample
could move the national 75-and-over figure (:func:`dgt_stats.exposure_risk.national.
older_sensitivity`, source ``older sample``). It is not an estimate of anyone's driving.

Only aggregates are published, under the survey's rule of 20 sample observations a cell
(:mod:`publication`).
"""

from __future__ import annotations

import pandas as pd

from dgt_stats.emef import ingest, publication
from dgt_stats.emef import variables as v

ROUTING_COLUMN = "V01B"
EMPLOYED_CODE = 1
OLDER_LABEL = "65+"
ROUTING_YEARS = (2022, 2023, 2024)


def routing_flag(year: int) -> pd.DataFrame:
    """One row per respondent of ``year``: sex, the 65-and-over flag, the weight, and whether the
    routing identifies a retiree aged 75 or over (aged 65+, not in work, ``V01B`` blank)."""
    raw = ingest.read_raw(year, "persons")
    labels = v.age_labels(year)
    age = pd.to_numeric(raw[v.AGE_COLUMN[year][1]].replace("", None)).map(labels)
    status = pd.to_numeric(raw[v.EMPLOYMENT_COLUMN[year]].replace("", None))
    sex = pd.to_numeric(raw[v.SEX_COLUMN[year]].replace("", None)).map(v.SEX_LABELS)
    older = (age == OLDER_LABEL).to_numpy()
    flagged = older & (status != EMPLOYED_CODE).to_numpy() & (raw[ROUTING_COLUMN] == "").to_numpy()
    return pd.DataFrame(
        {
            "year": year,
            "sex": sex.to_numpy(),
            "older": older,
            "weight": pd.to_numeric(raw["PESAIX"].str.replace(",", ".", regex=False)).to_numpy(),
            "retiree_75_plus": flagged,
        }
    )


def routing_share(years: tuple[int, ...] = ROUTING_YEARS) -> pd.DataFrame:
    """By sex: the weighted share of the survey's 65-and-over respondents that the routing
    identifies as retirees aged 75 or over, ``years`` pooled, beside the share aged 75 and over
    among residents of the province of Barcelona aged 65 and over (INE, 1 July, mean of the
    years)."""
    from dgt_stats.exposure_risk import national

    frame = pd.concat([routing_flag(year) for year in years], ignore_index=True)
    frame = frame[frame.older]
    population = national.barcelona_older_population(years).set_index(["sex", "group"]).population
    rows = []
    for sex in national.SEXES:
        part = frame[frame.sex == sex]
        old, young = population[(sex, "75+")], population[(sex, "65-74")]
        rows.append(
            {
                "years": "-".join(map(str, years)),
                "sex": sex,
                "respondents_65_plus": int(len(part)),
                "respondents_flagged": int(part.retiree_75_plus.sum()),
                "routing_share_75_plus": float(
                    part.weight[part.retiree_75_plus].sum() / part.weight.sum()
                ),
                "ine_share_75_plus": float(old / (old + young)),
            }
        )
    out = pd.DataFrame(rows)
    return publication.suppress_small_cells(out, "respondents_flagged", ["routing_share_75_plus"])
