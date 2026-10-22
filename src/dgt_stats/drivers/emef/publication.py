"""The EMEF's rule for publishing results from its public-use microdata.

Every edition's dictionary (``data/raw/emef/<year>/emef_<year>_dictionary.xlsx``, sheet
``Sumari``, note 3) sets the precision requirements Eurostat sets and Idescat adopted: an estimate
is reliable and may be published only if the cell has at least 20 sample observations, and a table
only if at least 60% of its cells have valid values; cells that may not be published are marked
"..". The published tables leave such a cell's estimates empty and keep its sample count, so that
the reason is visible; a ``suppressed`` column flags the row where a table can have one.

The rule is about precision, not confidentiality, so no second cell is hidden to stop a suppressed
share being recovered as the complement of the others.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

MIN_SAMPLE_OBSERVATIONS = 20
MIN_VALID_CELL_SHARE = 0.6


def suppress_small_cells(
    frame: pd.DataFrame,
    count: str,
    estimates: Iterable[str],
    flag: bool = False,
) -> pd.DataFrame:
    """``frame`` with ``estimates`` left empty in every row whose ``count`` of sample observations
    is below :data:`MIN_SAMPLE_OBSERVATIONS`; with ``flag``, a ``suppressed`` column marks them.

    Raises if fewer than :data:`MIN_VALID_CELL_SHARE` of the estimate cells can be published, when
    the rule does not allow the table at all."""
    columns = list(estimates)
    out = frame.copy()
    small = out[count].astype(float) < MIN_SAMPLE_OBSERVATIONS
    if columns and len(out):
        valid = out[columns].notna() & ~small.to_numpy()[:, None]
        share = float(valid.to_numpy().mean())
        if share < MIN_VALID_CELL_SHARE:
            raise ValueError(
                f"only {share:.0%} of the cells of {columns} rest on {MIN_SAMPLE_OBSERVATIONS} or "
                "more sample observations: the EMEF's rule does not allow the table"
            )
    out[columns] = out[columns].astype(float)
    out.loc[small, columns] = float("nan")
    if flag:
        out["suppressed"] = small.to_numpy()
    return out
