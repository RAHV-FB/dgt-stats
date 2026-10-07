"""Audit of the Barcelona coordinates: which column holds the easting, and do UTM and WGS84 agree.

Each Barcelona file carries ``Coordenada_UTM_X_ED50``, ``Coordenada_UTM_Y_ED50`` (UTM zone 31N on
the ED50 datum, metres) and ``Longitud_WGS84``/``Latitud_WGS84``. In Spain a UTM easting is always
below 1,000,000 m and a northing above 3,000,000 m, so the magnitude of a value says which one it
is whatever its column is called. The audit applies that rule row by row, reports for each file
how many rows carry an easting under the "Y" label, and checks the result two ways:

* against the same crash in the other files (same ``Numero_expedient``), and
* against the WGS84 position projected to UTM 31N: the two should differ by one near-constant
  offset (the ED50 to WGS84 datum shift), so a small spread around that offset confirms the pairs.

The corrected columns ``utm_x_ed50``/``utm_y_ed50`` are added beside the untouched source columns
with ``utm_labels_swapped_in_source`` saying where the labels were exchanged. Maps use WGS84.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dgt_stats.microdata.common import to_float

X_LABEL = "Coordenada_UTM_X_ED50"
Y_LABEL = "Coordenada_UTM_Y_ED50"
EASTING_MAX = 1_000_000.0
NORTHING_MIN = 3_000_000.0


def corrected_utm(frame: pd.DataFrame, table: str) -> pd.DataFrame:
    """Easting and northing by magnitude, with a flag where the source labels were exchanged."""
    x = to_float(frame[X_LABEL]).astype(float)
    y = to_float(frame[Y_LABEL]).astype(float)
    swapped = (x > NORTHING_MIN) & (y < EASTING_MAX)
    regular = (x < EASTING_MAX) & (y > NORTHING_MIN)
    out = pd.DataFrame(index=frame.index)
    out["utm_x_ed50"] = np.where(swapped, y, np.where(regular, x, np.nan))
    out["utm_y_ed50"] = np.where(swapped, x, np.where(regular, y, np.nan))
    out["utm_labels_swapped_in_source"] = swapped.astype(bool)
    out["utm_unresolved"] = ~(swapped | regular)
    return out


def utm_from_wgs84(longitude: np.ndarray, latitude: np.ndarray, zone: int = 31):
    """Project WGS84 degrees to UTM metres (Snyder's transverse Mercator series)."""
    a = 6378137.0
    f = 1 / 298.257223563
    k0 = 0.9996
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    lat = np.radians(np.asarray(latitude, dtype=float))
    lon = np.radians(np.asarray(longitude, dtype=float))
    lon0 = np.radians((zone - 1) * 6 - 180 + 3)
    n = a / np.sqrt(1 - e2 * np.sin(lat) ** 2)
    t = np.tan(lat) ** 2
    c = ep2 * np.cos(lat) ** 2
    big_a = np.cos(lat) * (lon - lon0)
    e4, e6 = e2 * e2, e2 * e2 * e2
    m = a * (
        (1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * lat
        - (3 * e2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * np.sin(2 * lat)
        + (15 * e4 / 256 + 45 * e6 / 1024) * np.sin(4 * lat)
        - (35 * e6 / 3072) * np.sin(6 * lat)
    )
    easting = (
        k0
        * n
        * (
            big_a
            + (1 - t + c) * big_a**3 / 6
            + (5 - 18 * t + t * t + 72 * c - 58 * ep2) * big_a**5 / 120
        )
        + 500000.0
    )
    northing = k0 * (
        m
        + n
        * np.tan(lat)
        * (
            big_a**2 / 2
            + (5 - t + 9 * c + 4 * c * c) * big_a**4 / 24
            + (61 - 58 * t + t * t + 600 * c - 330 * ep2) * big_a**6 / 720
        )
    )
    return easting, northing


def audit(tables: dict[str, pd.DataFrame], key: str, reference: str) -> pd.DataFrame:
    """One row per file: label orientation, agreement with the reference file and with WGS84."""
    ref = tables[reference]
    ref_utm = corrected_utm(ref, reference).assign(**{key: ref[key].values})
    ref_utm = ref_utm.drop_duplicates(key).set_index(key)
    rows = []
    for name, frame in tables.items():
        utm = corrected_utm(frame, name)
        lon = to_float(frame["Longitud_WGS84"]).astype(float).to_numpy()
        lat = to_float(frame["Latitud_WGS84"]).astype(float).to_numpy()
        east, north = utm_from_wgs84(lon, lat)
        dx = utm.utm_x_ed50.to_numpy() - east
        dy = utm.utm_y_ed50.to_numpy() - north
        joined = utm.assign(**{key: frame[key].values}).join(
            ref_utm[["utm_x_ed50", "utm_y_ed50"]], on=key, rsuffix="_ref"
        )
        same = np.isclose(joined.utm_x_ed50, joined.utm_x_ed50_ref) & np.isclose(
            joined.utm_y_ed50, joined.utm_y_ed50_ref
        )
        raw_x = to_float(frame[X_LABEL]).astype(float)
        rows.append(
            {
                "table": name,
                "rows": len(frame),
                "header_order": "Y before X"
                if list(frame.columns).index(Y_LABEL) < list(frame.columns).index(X_LABEL)
                else "X before Y",
                "rows_x_label_holds_easting": int(
                    utm.utm_labels_swapped_in_source.eq(False).sum() - utm.utm_unresolved.sum()
                ),
                "rows_x_label_holds_northing": int(utm.utm_labels_swapped_in_source.sum()),
                "rows_unresolved": int(utm.utm_unresolved.sum()),
                "x_label_min": float(raw_x.min()),
                "x_label_max": float(raw_x.max()),
                "share_matching_reference_after_correction": float(np.mean(same)),
                "wgs84_lon_min": float(np.nanmin(lon)),
                "wgs84_lon_max": float(np.nanmax(lon)),
                "wgs84_lat_min": float(np.nanmin(lat)),
                "wgs84_lat_max": float(np.nanmax(lat)),
                "offset_east_median_m": float(np.nanmedian(dx)),
                "offset_north_median_m": float(np.nanmedian(dy)),
                "offset_spread_p99_m": float(
                    np.nanpercentile(np.hypot(dx - np.nanmedian(dx), dy - np.nanmedian(dy)), 99)
                ),
                "offset_spread_max_m": float(
                    np.nanmax(np.hypot(dx - np.nanmedian(dx), dy - np.nanmedian(dy)))
                ),
            }
        )
    return pd.DataFrame(rows)
