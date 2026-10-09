"""Spain's autonomous communities and cities, and the provinces that make each.

DGT's crash records name the province by its INE code (``COD_PROVINCIA``, 1 to 52); INE's
territorial classification groups them into seventeen autonomous communities and the two
autonomous cities. The names are in English where English has a usual form.
"""

from __future__ import annotations

import pandas as pd

# The communities in INE's order of their codes (01 Andalusia to 19 Melilla), each with its
# provinces' INE codes.
COMMUNITIES: dict[str, tuple[int, ...]] = {
    "Andalusia": (4, 11, 14, 18, 21, 23, 29, 41),
    "Aragon": (22, 44, 50),
    "Asturias": (33,),
    "Balearic Islands": (7,),
    "Canary Islands": (35, 38),
    "Cantabria": (39,),
    "Castile and León": (5, 9, 24, 34, 37, 40, 42, 47, 49),
    "Castile-La Mancha": (2, 13, 16, 19, 45),
    "Catalonia": (8, 17, 25, 43),
    "Valencian Community": (3, 12, 46),
    "Extremadura": (6, 10),
    "Galicia": (15, 27, 32, 36),
    "Madrid": (28,),
    "Murcia": (30,),
    "Navarre": (31,),
    "Basque Country": (1, 20, 48),
    "La Rioja": (26,),
    "Ceuta": (51,),
    "Melilla": (52,),
}
COMMUNITY_BY_PROVINCE: dict[int, str] = {
    province: community for community, provinces in COMMUNITIES.items() for province in provinces
}


def community(province: pd.Series) -> pd.Series:
    """The community of each province code; a code outside 1-52 raises, so none goes missing."""
    codes = pd.to_numeric(province, errors="coerce")
    out = codes.map(COMMUNITY_BY_PROVINCE)
    unknown = sorted(set(codes[out.isna()].dropna().astype(int)))
    if out.isna().any():
        raise ValueError(f"province codes with no community: {unknown or 'missing'}")
    return out.astype("string")
