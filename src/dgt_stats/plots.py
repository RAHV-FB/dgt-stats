"""Chart functions for the site. Every function writes one SVG and returns its path.

Rules applied throughout: one y-axis per chart, categorical hues assigned in a fixed order, a legend
whenever there are two or more series, thin marks, recessive hairline grid, text in text colours
rather than series colours, and SVG output without a timestamp so rebuilds are byte-stable.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

matplotlib.use("Agg")

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e6e5e1"

# Fixed categorical order (validated for adjacent-pair colour-vision separation on the light surface).
CATEGORICAL: tuple[str, ...] = (
    "#2a78d6",
    "#eb6834",
    "#1baf7a",
    "#eda100",
    "#e87ba4",
    "#008300",
    "#4a3aa7",
    "#e34948",
)

# One-hue sequential ramp, light to dark.
SEQUENTIAL: tuple[str, ...] = (
    "#cde2fb",
    "#b7d3f6",
    "#9ec5f4",
    "#86b6ef",
    "#6da7ec",
    "#5598e7",
    "#3987e5",
    "#2a78d6",
    "#256abf",
    "#1c5cab",
    "#184f95",
    "#104281",
    "#0d366b",
)

SEQUENTIAL_CMAP = LinearSegmentedColormap.from_list("blue_ramp", list(SEQUENTIAL))

FIGURE_WIDTH = 8.0


def apply_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "font.family": ["DejaVu Sans", "sans-serif"],
            "font.size": 10,
            "text.color": TEXT_PRIMARY,
            "axes.labelcolor": TEXT_SECONDARY,
            "axes.edgecolor": GRID,
            "axes.linewidth": 1,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.titlepad": 12,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "grid.color": GRID,
            "grid.linewidth": 1,
            "grid.linestyle": "-",
            "axes.axisbelow": True,
            "xtick.color": TEXT_SECONDARY,
            "ytick.color": TEXT_SECONDARY,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "lines.linewidth": 2,
            "lines.solid_joinstyle": "round",
            "lines.solid_capstyle": "round",
            "legend.frameon": False,
            "legend.fontsize": 9,
            "svg.fonttype": "none",
            "svg.hashsalt": "dgt-stats",
            "figure.dpi": 100,
        }
    )


def save(fig: plt.Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, format="svg", metadata={"Date": None}, bbox_inches="tight")
    plt.close(fig)
    return path


def caption(source: str, period: str, definition: str, n: str | int | None = None) -> str:
    parts = [f"Source: {source}", f"Period: {period}", f"Definition: {definition}"]
    if n is not None:
        parts.append(f"n = {n:,}" if isinstance(n, int) else f"n = {n}")
    return ". ".join(parts) + "."


def _thousands(axis: plt.Axes) -> None:
    axis.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))


def _percent(axis: plt.Axes, decimals: int = 0) -> None:
    axis.yaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda v, _: f"{v * 100:.{decimals}f}%")
    )


def line_series(
    frame: pd.DataFrame,
    x: str,
    y: str,
    path: Path,
    title: str,
    series: str | None = None,
    ylabel: str = "",
    percent: bool = False,
    zero_based: bool = True,
    reference: float | None = None,
    height: float = 4.2,
    end_labels: bool = True,
) -> Path:
    """One or more lines on a single axis; legend plus end labels when there are 2–4 series.

    Pass ``end_labels=False`` when the series converge at the right edge (indexed charts).
    """
    apply_style()
    fig, axis = plt.subplots(figsize=(FIGURE_WIDTH, height))
    groups = [(None, frame)] if series is None else list(frame.groupby(series, sort=False))
    if len(groups) > len(CATEGORICAL):
        raise ValueError("more series than fixed colours; fold to 'Other' or facet")
    for index, (name, group) in enumerate(groups):
        group = group.sort_values(x)
        colour = CATEGORICAL[index]
        axis.plot(group[x], group[y], color=colour, label=None if name is None else str(name))
        last = group.dropna(subset=[y]).iloc[-1] if group[y].notna().any() else None
        if last is not None:
            axis.plot(
                [last[x]],
                [last[y]],
                marker="o",
                markersize=8,
                color=colour,
                markeredgecolor=SURFACE,
                markeredgewidth=2,
                linestyle="none",
            )
            if end_labels and name is not None and len(groups) <= 4:
                axis.annotate(
                    str(name),
                    (last[x], last[y]),
                    xytext=(6, 0),
                    textcoords="offset points",
                    va="center",
                    fontsize=9,
                    color=TEXT_SECONDARY,
                )
    if reference is not None:
        axis.axhline(reference, color=TEXT_SECONDARY, linewidth=1, linestyle=":")
    if zero_based:
        axis.set_ylim(bottom=0)
    if percent:
        _percent(axis)
    else:
        _thousands(axis)
    axis.set_title(title)
    axis.set_ylabel(ylabel)
    axis.set_xlabel("")
    if len(groups) >= 2:
        axis.legend(loc="upper left", bbox_to_anchor=(0, -0.12), ncol=min(len(groups), 4))
    return save(fig, path)


def bar_shares(
    frame: pd.DataFrame,
    x: str,
    series: str,
    value: str,
    path: Path,
    title: str,
    order: list[str] | None = None,
    height: float = 4.6,
) -> Path:
    """Stacked 100 % bars, one colour per series in fixed order, 2 px surface gaps between segments."""
    apply_style()
    wide = frame.pivot_table(index=x, columns=series, values=value, aggfunc="sum").fillna(0)
    if order:
        wide = wide.reindex(columns=[c for c in order if c in wide.columns])
    if wide.shape[1] > len(CATEGORICAL):
        raise ValueError("more series than fixed colours; fold to 'Other'")
    shares = wide.div(wide.sum(axis=1), axis=0)
    fig, axis = plt.subplots(figsize=(FIGURE_WIDTH, height))
    bottom = np.zeros(len(shares))
    positions = np.arange(len(shares))
    for index, column in enumerate(shares.columns):
        values = shares[column].to_numpy()
        axis.bar(
            positions,
            values,
            bottom=bottom,
            width=0.72,
            color=CATEGORICAL[index],
            edgecolor=SURFACE,
            linewidth=2,
            label=str(column),
        )
        bottom = bottom + values
    axis.set_xticks(positions, [str(v) for v in shares.index])
    axis.set_ylim(0, 1)
    _percent(axis)
    axis.set_title(title)
    axis.legend(loc="upper left", bbox_to_anchor=(0, -0.1), ncol=4)
    return save(fig, path)


def heatmap(
    matrix: pd.DataFrame,
    path: Path,
    title: str,
    value_format: str = "{:.0f}",
    annotate: bool | None = None,
    percent: bool = False,
    height: float | None = None,
    xlabel: str = "",
    ylabel: str = "",
) -> Path:
    """Sequential one-hue heatmap of a rows × columns matrix; cells annotated when there are few."""
    apply_style()
    rows, cols = matrix.shape
    height = height or max(2.5, 0.28 * rows + 1.6)
    fig, axis = plt.subplots(figsize=(FIGURE_WIDTH, height))
    values = matrix.to_numpy(dtype=float)
    image = axis.imshow(values, cmap=SEQUENTIAL_CMAP, aspect="auto")
    axis.grid(False)
    axis.set_xticks(range(cols), [str(c) for c in matrix.columns], fontsize=8)
    axis.set_yticks(range(rows), [str(r) for r in matrix.index], fontsize=8)
    axis.tick_params(length=0)
    for spine in axis.spines.values():
        spine.set_visible(False)
    if annotate is None:
        annotate = rows * cols <= 60
    if annotate:
        threshold = np.nanmin(values) + 0.55 * (np.nanmax(values) - np.nanmin(values))
        for r in range(rows):
            for c in range(cols):
                cell = values[r, c]
                if np.isnan(cell):
                    continue
                text = f"{cell * 100:.0f}%" if percent else value_format.format(cell)
                axis.text(
                    c,
                    r,
                    text,
                    ha="center",
                    va="center",
                    fontsize=8,
                    color=SURFACE if cell >= threshold else TEXT_PRIMARY,
                )
    bar = fig.colorbar(image, ax=axis, fraction=0.03, pad=0.02)
    bar.outline.set_visible(False)
    if percent:
        bar.formatter = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v * 100:.0f}%")
        bar.update_ticks()
    axis.set_title(title)
    axis.set_xlabel(xlabel)
    axis.set_ylabel(ylabel)
    return save(fig, path)


def small_multiples(
    frame: pd.DataFrame,
    facet: str,
    x: str,
    y: str,
    path: Path,
    title: str,
    ncols: int = 3,
    percent: bool = False,
    shared_y: bool = False,
    order: list[str] | None = None,
) -> Path:
    """One small line chart per facet value, same x range, each panel labelled by its facet."""
    apply_style()
    facets = order or list(dict.fromkeys(frame[facet]))
    nrows = int(np.ceil(len(facets) / ncols))
    fig, axes = plt.subplots(
        nrows, ncols, figsize=(FIGURE_WIDTH, 2.2 * nrows + 0.6), sharex=True, sharey=shared_y
    )
    axes = np.atleast_1d(axes).ravel()
    for index, name in enumerate(facets):
        axis = axes[index]
        group = frame[frame[facet] == name].sort_values(x)
        axis.plot(group[x], group[y], color=CATEGORICAL[0])
        axis.set_title(str(name), fontsize=10, fontweight="normal")
        axis.set_ylim(bottom=0)
        if percent:
            _percent(axis)
        else:
            _thousands(axis)
        axis.tick_params(labelsize=8)
    for axis in axes[len(facets) :]:
        axis.set_visible(False)
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.tight_layout()
    return save(fig, path)


def missingness_heatmap(profile: pd.DataFrame, path: Path, title: str) -> Path:
    """Year × column share of observed (non-missing) values."""
    matrix = profile.pivot(index="column", columns="year", values="share_observed")
    return heatmap(
        matrix,
        path,
        title,
        percent=True,
        annotate=False,
        height=max(4.0, 0.22 * len(matrix) + 1.5),
        xlabel="Year",
    )
