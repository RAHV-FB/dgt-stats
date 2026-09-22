"""Chart functions for the site. Every function writes one SVG and returns its path.

Rules applied throughout: one y-axis per chart, series colours assigned in a fixed order and paired
with a line style or marker on every line chart, so that colour is never the only difference
between lines; the bar charts separate their series by colour and by position in a fixed order; a
legend when there are two or more series, thin lines, a faint grid, labels in black or grey rather
than in the series colour, and SVG output without a timestamp, so an unchanged figure does not
churn on rebuild.
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

# Categorical colours in the order series take them; neighbouring pairs stay distinct under
# red-green colour-vision deficiency.
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

# Line styles and marker shapes cycled alongside the colours, so that series can still be told
# apart in greyscale or with a colour-vision deficiency. The first four series differ by dash
# pattern alone; the next four repeat the dash patterns and add a marker on every point.
LINE_STYLES: tuple[str, ...] = ("-", "--", "-.", ":")
MARKERS: tuple[str, ...] = ("o", "s", "^", "D")

FIGURE_WIDTH = 8.0


def _series_style(index: int) -> dict[str, object]:
    """Keyword arguments for ``Axes.plot`` that give series ``index`` its own dash pattern."""
    style: dict[str, object] = {"linestyle": LINE_STYLES[index % len(LINE_STYLES)]}
    if index >= len(LINE_STYLES):
        style.update(marker=MARKERS[(index - len(LINE_STYLES)) % len(MARKERS)], markersize=4)
    return style


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


def _tick(value: float, _: object = None) -> str:
    """Thousands separators, and up to two decimals only when the tick is not a whole number."""
    if float(value).is_integer():
        return f"{value:,.0f}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _thousands(axis: plt.Axes) -> None:
    axis.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(_tick))


def _integer_x(axis: plt.Axes, nbins: int | str = "auto") -> None:
    """Whole-number x ticks (years); ``nbins`` limits the count in small panels."""
    axis.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(nbins=nbins, integer=True))


def _percent_text(value: float, decimals: int | None = None, signed: bool = False) -> str:
    """A share as a percentage: fixed ``decimals`` when given, otherwise up to two and only when
    the tick is not a whole percentage, so 2.5% and 7.5% are not both printed as 2% and 8%."""
    scaled = value * 100
    if decimals is not None:
        text = f"{scaled:.{decimals}f}"
    else:
        text = f"{scaled:.2f}".rstrip("0").rstrip(".")
    if float(text) == 0:
        text = text.lstrip("-")  # never "+0%" or "-0%"
    elif signed and not text.startswith("-"):
        text = f"+{text}"
    return f"{text}%"


def _percent(axis: plt.Axes, decimals: int | None = None) -> None:
    axis.yaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda v, _: _percent_text(v, decimals))
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
    band: tuple[str, str] | None = None,
) -> Path:
    """One or more lines on a single axis; legend plus end labels when there are 2–4 series.

    Pass ``end_labels=False`` when the series converge at the right edge (indexed charts) and
    ``band=(low_column, high_column)`` to shade an interval around each line.
    """
    apply_style()
    fig, axis = plt.subplots(figsize=(FIGURE_WIDTH, height))
    groups = [(None, frame)] if series is None else list(frame.groupby(series, sort=False))
    if len(groups) > len(CATEGORICAL):
        raise ValueError("more series than fixed colours; fold to 'Other' or facet")
    for index, (name, group) in enumerate(groups):
        group = group.sort_values(x)
        colour = CATEGORICAL[index]
        if band is not None:
            axis.fill_between(
                group[x], group[band[0]], group[band[1]], color=colour, alpha=0.15, linewidth=0
            )
        axis.plot(
            group[x],
            group[y],
            color=colour,
            label=None if name is None else str(name),
            **_series_style(index),
        )
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
    _integer_x(axis)
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
        unknown = sorted(set(map(str, wide.columns)) - set(order))
        if unknown:
            raise ValueError(f"series not in order: {unknown}")
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
                if percent:
                    text = f"{cell * 100:.1f}%" if cell < 0.1 else f"{cell * 100:.0f}%"
                else:
                    text = value_format.format(cell)
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
        # One decimal on every tick as soon as one tick is not a whole percentage, otherwise a
        # bar with ticks every half point would print the same label three times.
        whole = all(round(float(t) * 100, 6).is_integer() for t in bar.get_ticks())
        decimals = 0 if whole else 1
        bar.formatter = matplotlib.ticker.FuncFormatter(lambda v, _: _percent_text(v, decimals))
    else:
        bar.formatter = matplotlib.ticker.FuncFormatter(_tick)
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
    series: str | None = None,
    series_order: list[str] | None = None,
    band: tuple[str, str] | None = None,
) -> Path:
    """One small line chart per facet value, same x range, each panel labelled by its facet.

    With ``series`` every panel carries one line per series value in fixed colour order and a
    shared legend below the grid; ``band`` shades an interval around each line.
    """
    apply_style()
    facets = order or list(dict.fromkeys(frame[facet]))
    names = [None] if series is None else (series_order or list(dict.fromkeys(frame[series])))
    if len(names) > len(CATEGORICAL):
        raise ValueError("more series than fixed colours; fold to 'Other' or facet")
    nrows = int(np.ceil(len(facets) / ncols))
    fig, axes = plt.subplots(
        nrows, ncols, figsize=(FIGURE_WIDTH, 2.2 * nrows + 0.6), sharex=True, sharey=shared_y
    )
    axes = np.atleast_1d(axes).ravel()
    for index, facet_name in enumerate(facets):
        axis = axes[index]
        panel = frame[frame[facet] == facet_name]
        for colour_index, name in enumerate(names):
            group = panel if name is None else panel[panel[series] == name]
            group = group.sort_values(x)
            colour = CATEGORICAL[colour_index]
            if band is not None:
                axis.fill_between(
                    group[x], group[band[0]], group[band[1]], color=colour, alpha=0.15, linewidth=0
                )
            axis.plot(
                group[x],
                group[y],
                color=colour,
                label=None if name is None else str(name),
                **_series_style(colour_index),
            )
        axis.set_title(str(facet_name), fontsize=10, fontweight="normal")
        if percent:
            _percent(axis)
        else:
            _thousands(axis)
        _integer_x(axis, nbins=4)
        axis.tick_params(labelsize=8)
    for axis in axes[: len(facets)]:
        axis.set_ylim(bottom=0)  # after every panel is drawn, so shared axes keep the full range
    for axis in axes[len(facets) :]:
        axis.set_visible(False)
    # Shared x axes only label the bottom row; when the last row is incomplete, the panels above
    # a hidden slot are the last visible ones in their column and need the x labels back.
    for index in range(len(facets)):
        if index + ncols >= len(facets):
            axes[index].tick_params(labelbottom=True)
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, fontweight="bold")
    if series is not None:
        handles, labels = axes[0].get_legend_handles_labels()
        legend_rows = int(np.ceil(len(names) / 4))
        fig.legend(
            handles,
            labels,
            loc="lower left",
            bbox_to_anchor=(0.01, 0.0),
            ncol=min(len(names), 4),
        )
        fig.tight_layout(rect=(0, 0.05 + 0.05 * legend_rows, 1, 1))
    else:
        fig.tight_layout()
    return save(fig, path)


def dot_interval(
    frame: pd.DataFrame,
    label: str,
    value: str,
    low: str,
    high: str,
    path: Path,
    title: str,
    xlabel: str = "",
    reference: float | None = None,
    reference_label: str = "",
    percent: bool = False,
    highlight: str | None = None,
    keep_order: bool = False,
) -> Path:
    """Ranked dots with interval whiskers, one row per label, highest value at the top.

    ``keep_order`` keeps the frame's own order (first row at the top) instead of ranking;
    ``highlight`` names a boolean column whose rows get a filled accent marker while the others
    are drawn hollow, for a true estimate among placebos.
    """
    apply_style()
    if keep_order:
        ordered = frame.iloc[::-1].reset_index(drop=True)
    else:
        ordered = frame.sort_values(value, ascending=True).reset_index(drop=True)
    height = max(3.0, 0.22 * len(ordered) + 1.4)
    fig, axis = plt.subplots(figsize=(FIGURE_WIDTH, height))
    positions = np.arange(len(ordered))
    flags = (
        ordered[highlight].astype(bool).to_numpy()
        if highlight is not None
        else np.ones(len(ordered), dtype=bool)
    )
    axis.hlines(
        positions, ordered[low], ordered[high], color=CATEGORICAL[0], linewidth=1.5, alpha=0.6
    )
    for filled in (False, True):
        mask = flags == filled
        if not mask.any():
            continue
        axis.plot(
            ordered[value][mask],
            positions[mask],
            marker="o",
            markersize=6 if filled else 5,
            color=CATEGORICAL[0],
            markerfacecolor=CATEGORICAL[0] if filled else SURFACE,
            markeredgecolor=SURFACE if filled else CATEGORICAL[0],
            markeredgewidth=1,
            linestyle="none",
        )
    if reference is not None:
        axis.axvline(reference, color=TEXT_SECONDARY, linewidth=1, linestyle=":")
        if reference_label:
            axis.annotate(
                reference_label,
                (reference, len(ordered) - 0.5),
                xytext=(4, 0),
                textcoords="offset points",
                fontsize=8,
                color=TEXT_SECONDARY,
                va="top",
            )
    axis.set_yticks(positions, [str(v) for v in ordered[label]], fontsize=8)
    axis.grid(True, axis="x")
    axis.grid(False, axis="y")
    if float(ordered[low].min()) >= 0:
        axis.set_xlim(left=0)
    if percent:
        signed = float(ordered[low].min()) < 0  # changes carry a sign, shares do not
        axis.xaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(lambda v, _: _percent_text(v, signed=signed))
        )
    axis.set_ylim(-0.7, len(ordered) - 0.3)
    axis.set_title(title)
    axis.set_xlabel(xlabel)
    return save(fig, path)


def forest(
    frame: pd.DataFrame,
    group: str,
    label: str,
    value: str,
    low: str,
    high: str,
    path: Path,
    title: str,
    xlabel: str = "Odds ratio (log scale)",
    reference_flag: str | None = None,
) -> Path:
    """Odds ratios on a log axis, one row per level, grouped by predictor with group headings.

    Rows flagged by ``reference_flag`` are drawn as hollow markers at 1 with no whisker. A level
    the fit could not estimate (no crashes of the modelled outcome, so no odds ratio) is left out
    of the plot altogether rather than drawn as a labelled but empty row; the caption names it.
    """
    apply_style()
    estimable = frame[value].notna()
    if reference_flag is not None:
        estimable = estimable | frame[reference_flag].astype(bool)
    frame = frame[estimable]
    rows: list[tuple[str, pd.Series | None]] = []
    for name, block in frame.groupby(group, sort=False):
        rows.append((str(name), None))
        for _, row in block.iterrows():
            rows.append((str(row[label]), row))
    height = max(3.5, 0.24 * len(rows) + 1.2)
    fig, axis = plt.subplots(figsize=(FIGURE_WIDTH, height))
    positions = np.arange(len(rows))[::-1]
    tick_labels = []
    for position, (text, row) in zip(positions, rows):
        if row is None:
            tick_labels.append(text)
            continue
        tick_labels.append("    " + text)
        is_reference = bool(row[reference_flag]) if reference_flag else False
        if is_reference:
            axis.plot(
                [1.0],
                [position],
                marker="o",
                markersize=6,
                markerfacecolor=SURFACE,
                markeredgecolor=CATEGORICAL[0],
                markeredgewidth=1.5,
                linestyle="none",
            )
            continue
        axis.hlines(position, row[low], row[high], color=CATEGORICAL[0], linewidth=1.5)
        axis.plot(
            [row[value]],
            [position],
            marker="o",
            markersize=6,
            color=CATEGORICAL[0],
            markeredgecolor=SURFACE,
            markeredgewidth=1,
            linestyle="none",
        )
    axis.axvline(1.0, color=TEXT_SECONDARY, linewidth=1, linestyle=":")
    axis.set_xscale("log")
    axis.set_yticks(positions, tick_labels, fontsize=8)
    for tick, (_, row) in zip(axis.get_yticklabels(), rows):
        if row is None:
            tick.set_fontweight("bold")
    # Labelled ticks at each doubling either side of 1; the default log locator labels only the
    # powers of ten, which leaves everything between 1 and 10 without a number.
    axis.xaxis.set_major_locator(matplotlib.ticker.FixedLocator([0.1, 0.25, 0.5, 1, 2, 4, 8]))
    axis.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    axis.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    axis.grid(True, axis="x")
    axis.grid(False, axis="y")
    axis.set_ylim(-0.7, len(rows) - 0.3)
    axis.set_title(title)
    axis.set_xlabel(xlabel)
    return save(fig, path)


def calibration(
    frame: pd.DataFrame,
    predicted: str,
    observed: str,
    path: Path,
    title: str,
    series: str | None = None,
) -> Path:
    """Observed share against mean predicted probability by decile, with the diagonal."""
    apply_style()
    fig, axis = plt.subplots(figsize=(FIGURE_WIDTH, 4.6))
    groups = [(None, frame)] if series is None else list(frame.groupby(series, sort=False))
    top = 0.0
    for index, (name, group) in enumerate(groups):
        group = group.sort_values(predicted)
        axis.plot(
            group[predicted],
            group[observed],
            marker=MARKERS[index % len(MARKERS)],
            markersize=6,
            linestyle=LINE_STYLES[index % len(LINE_STYLES)],
            color=CATEGORICAL[index],
            markeredgecolor=SURFACE,
            markeredgewidth=1,
            label=None if name is None else str(name),
        )
        top = max(top, float(group[[predicted, observed]].max().max()))
    axis.plot([0, top * 1.05], [0, top * 1.05], color=TEXT_SECONDARY, linewidth=1, linestyle=":")
    axis.set_xlim(0, top * 1.05)
    axis.set_ylim(0, top * 1.05)
    _percent(axis, 1)
    axis.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v * 100:.1f}%"))
    axis.set_title(title)
    axis.set_xlabel("Mean predicted probability in the decile")
    axis.set_ylabel("Observed share")
    if len(groups) >= 2:
        axis.legend(loc="upper left", bbox_to_anchor=(0, -0.14), ncol=min(len(groups), 4))
    return save(fig, path)


def grouped_bars(
    frame: pd.DataFrame,
    x: str,
    series: str,
    value: str,
    path: Path,
    title: str,
    order: list[str] | None = None,
    series_order: list[str] | None = None,
    percent: bool = False,
    ylabel: str = "",
    height: float = 4.2,
    xlabel: str = "",
    full_scale: bool = True,
) -> Path:
    """Side-by-side bars per category, one colour per series in fixed order.

    With ``percent`` the axis runs to 100 % unless ``full_scale`` is off, in which case it stops
    just above the tallest bar; many categories get rotated tick labels.
    """
    apply_style()
    wide = frame.pivot_table(index=x, columns=series, values=value, aggfunc="first")
    if order:
        wide = wide.reindex(order)
    if series_order:
        wide = wide.reindex(columns=series_order)
    if wide.shape[1] > len(CATEGORICAL):
        raise ValueError("more series than fixed colours")
    fig, axis = plt.subplots(figsize=(FIGURE_WIDTH, height))
    n_series = wide.shape[1]
    width = 0.8 / n_series
    positions = np.arange(len(wide))
    for index, column in enumerate(wide.columns):
        offset = (index - (n_series - 1) / 2) * width
        axis.bar(
            positions + offset,
            wide[column].to_numpy(dtype=float),
            width=width * 0.92,
            color=CATEGORICAL[index],
            label=str(column),
        )
    rotation = 45 if len(wide) > 8 else 0
    axis.set_xticks(
        positions,
        [str(v) for v in wide.index],
        rotation=rotation,
        ha="right" if rotation else "center",
    )
    axis.set_ylim(bottom=0)
    if percent:
        top = 1.0 if full_scale else min(1.0, float(np.nanmax(wide.to_numpy(dtype=float))) * 1.15)
        axis.set_ylim(0, top)
        _percent(axis)
    else:
        _thousands(axis)
    axis.set_title(title)
    axis.set_ylabel(ylabel)
    axis.set_xlabel(xlabel)
    axis.legend(
        loc="upper left", bbox_to_anchor=(0, -0.18 if rotation else -0.1), ncol=min(n_series, 4)
    )
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


def dot_interval_panels(
    frame: pd.DataFrame,
    panel: str,
    label: str,
    value: str,
    low: str,
    high: str,
    path: Path,
    title: str,
    order: list[str] | None = None,
    panel_order: list[str] | None = None,
    xlabel: str = "",
) -> Path:
    """Side-by-side dot-and-whisker panels sharing one row order (``order``, top to bottom).

    Each panel has its own x scale from zero, so the panels compare rankings, not magnitudes.
    """
    apply_style()
    labels_order = order or list(dict.fromkeys(frame[label]))
    panels = panel_order or list(dict.fromkeys(frame[panel]))
    height = max(2.8, 0.34 * len(labels_order) + 1.6)
    fig, axes = plt.subplots(
        1, len(panels), figsize=(FIGURE_WIDTH, height), sharey=True, constrained_layout=True
    )
    axes = np.atleast_1d(axes)
    positions = np.arange(len(labels_order))[::-1]
    for axis, name in zip(axes, panels):
        block = frame[frame[panel] == name].set_index(label).reindex(labels_order)
        axis.hlines(
            positions, block[low], block[high], color=CATEGORICAL[0], linewidth=1.5, alpha=0.6
        )
        axis.plot(
            block[value],
            positions,
            marker="o",
            markersize=6,
            color=CATEGORICAL[0],
            markeredgecolor=SURFACE,
            markeredgewidth=1,
            linestyle="none",
        )
        axis.set_title(str(name), fontsize=10, fontweight="normal", loc="left")
        axis.grid(True, axis="x")
        axis.grid(False, axis="y")
        axis.set_xlim(left=0)
        axis.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(_tick))
        axis.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(nbins=4))
        axis.tick_params(labelsize=8)
        axis.set_xlabel(xlabel, fontsize=8)
    axes[0].set_yticks(positions, [str(v) for v in labels_order], fontsize=8)
    axes[0].set_ylim(-0.7, len(labels_order) - 0.3)
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, fontweight="bold")
    return save(fig, path)


def slope(
    frame: pd.DataFrame,
    label: str,
    left: str,
    right: str,
    path: Path,
    title: str,
    left_title: str,
    right_title: str,
    value_format: str = "{:,.1f}",
) -> Path:
    """Two ranked columns joined by a line per row: how each label moves between two measures.

    Rows are placed by rank on each side (highest value at the top); the values are printed next to
    the labels so the reader has the numbers, not only the order.
    """
    apply_style()
    n = len(frame)
    left_rank = frame[left].rank(ascending=False, method="first")
    right_rank = frame[right].rank(ascending=False, method="first")
    fig, axis = plt.subplots(figsize=(FIGURE_WIDTH, max(3.0, 0.42 * n + 1.4)))
    for index, (_, row) in enumerate(frame.iterrows()):
        y0, y1 = n - left_rank.iloc[index], n - right_rank.iloc[index]
        colour = CATEGORICAL[index % len(CATEGORICAL)]
        axis.plot([0, 1], [y0, y1], color=colour, linewidth=2, marker="o", markersize=6)
        axis.text(
            -0.03,
            y0,
            f"{row[label]}  {value_format.format(row[left])}",
            ha="right",
            va="center",
            fontsize=8,
        )
        axis.text(
            1.03,
            y1,
            f"{value_format.format(row[right])}  {row[label]}",
            ha="left",
            va="center",
            fontsize=8,
        )
    axis.text(0, n - 0.2, left_title, ha="center", va="bottom", fontsize=9, color=TEXT_SECONDARY)
    axis.text(1, n - 0.2, right_title, ha="center", va="bottom", fontsize=9, color=TEXT_SECONDARY)
    axis.set_xlim(-0.9, 1.9)
    axis.set_ylim(-0.6, n + 0.4)
    axis.axis("off")
    axis.set_title(title, loc="left", pad=18)
    return save(fig, path)


def intervention(
    frame: pd.DataFrame,
    x: str,
    observed: str,
    fitted: str,
    counterfactual: str,
    path: Path,
    title: str,
    break_date: pd.Timestamp,
    break_label: str,
    facet: str | None = None,
    facet_order: list[str] | None = None,
    shaded: list[tuple[pd.Timestamp, pd.Timestamp, str]] | None = None,
    ylabel: str = "",
    height: float | None = None,
) -> Path:
    """Observed monthly counts, the fitted line and the dashed counterfactual around a break.

    One panel, or one panel per ``facet`` value stacked with shared x and y axes, so that the
    groups a difference-in-differences design compares sit on one vertical scale. ``shaded``
    marks periods (for example a confounding change or the pandemic) with a labelled grey band.
    """
    apply_style()
    facets = [None] if facet is None else (facet_order or list(dict.fromkeys(frame[facet])))
    height = height or (3.6 if facet is None else 2.6 * len(facets) + 0.8)
    fig, axes = plt.subplots(
        len(facets), 1, figsize=(FIGURE_WIDTH, height), sharex=True, sharey=facet is not None
    )
    axes = np.atleast_1d(axes)
    for axis, name in zip(axes, facets):
        panel = frame if name is None else frame[frame[facet] == name]
        panel = panel.sort_values(x)
        axis.plot(
            panel[x],
            panel[observed],
            color=TEXT_SECONDARY,
            linewidth=1,
            alpha=0.7,
            marker="o",
            markersize=2.5,
            label="Observed",
        )
        axis.plot(panel[x], panel[fitted], color=CATEGORICAL[0], linewidth=2, label="Fitted")
        post = panel[panel[x] >= break_date]
        axis.plot(
            post[x],
            post[counterfactual],
            color=CATEGORICAL[1],
            linewidth=2,
            linestyle="--",
            label="Counterfactual (no change)",
        )
        axis.axvline(break_date, color=TEXT_PRIMARY, linewidth=1)
        for start, end, _ in shaded or []:
            axis.axvspan(start, end, color=GRID, alpha=0.6, linewidth=0)
        axis.set_ylim(bottom=0)
        _thousands(axis)
        axis.set_ylabel(ylabel, fontsize=9)
        if name is not None:
            axis.set_title(str(name), fontsize=10, fontweight="normal", loc="left")
    # Period labels go in once every panel is drawn, so they hang from the final (shared) top,
    # one step below the break label so the two never run into each other.
    for axis in axes:
        top = axis.get_ylim()[1]
        for index, (start, _, label) in enumerate(shaded or []):
            axis.text(
                start,
                top * (0.86 - 0.12 * index),  # stagger neighbouring labels
                f" {label}",
                fontsize=7,
                color=TEXT_SECONDARY,
                va="top",
            )
    axes[0].text(
        break_date,
        axes[0].get_ylim()[1] * 0.98,
        f" {break_label}",
        fontsize=8,
        color=TEXT_PRIMARY,
        va="top",
    )
    axes[-1].legend(loc="upper left", bbox_to_anchor=(0, -0.15), ncol=3)
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.tight_layout()
    return save(fig, path)
