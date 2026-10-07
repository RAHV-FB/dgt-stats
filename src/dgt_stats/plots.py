"""Chart functions for the site. Every function writes one SVG and returns its path.

The house style is restrained. One accent colour carries the series or estimate a chart is about;
context, reference and baseline series are drawn in greys, and every distinction that matters is
also made by line style, marker shape or a direct label, so no reading depends on colour alone.
Lines are labelled at their ends where the labels fit, legends are used otherwise, the grid is
faint and axes carry no box. The text is set in STIX Two Text, the serif of the site's technical
text, from the static fonts in ``dgt_stats/fonts``: matplotlib lays it out with them, and each
SVG embeds the glyphs it uses, so a chart reads the same on every system.

A chart's title is not drawn into the SVG: it is recorded in ``TITLES`` and printed above the
figure on the page, so that the title, the chart and the caption below it read as three parts.
The SVG is written without a timestamp, so an unchanged figure does not churn on rebuild.
"""

from __future__ import annotations

import base64
import html
import io
import re
import textwrap
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from fontTools import subset as font_subset
from fontTools.ttLib import TTFont
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap

matplotlib.use("Agg")

# The serif the chart text is set in, at the text weight and the weight of a few headings.
FONT_DIR = Path(__file__).resolve().parent / "fonts"
CHART_FONT = "STIX Two Text"
CHART_FONT_FILES = {
    400: FONT_DIR / "STIXTwoText-Regular.ttf",
    600: FONT_DIR / "STIXTwoText-SemiBold.ttf",
}
HEADING_WEIGHT = 600
for _font_file in CHART_FONT_FILES.values():
    font_manager.fontManager.addfont(str(_font_file))

SURFACE = "#ffffff"
TEXT_PRIMARY = "#1b1b1b"
TEXT_SECONDARY = "#555555"
GRID = "#ebebe8"
AXIS = "#b5b5b0"
# The accent is the colour of the series or estimate a chart is about, the site's turquoise-blue;
# the greys are for context.
ACCENT = "#1a8eab"
NEUTRAL = "#7d7d78"
NEUTRAL_LIGHT = "#bdbdb8"
REFERENCE = "#4f4f4f"

# Categorical colours, for the few charts whose categories are all of equal standing, in the order
# series take them. They are muted, and neighbouring pairs stay distinct under red-green
# colour-vision deficiency; each is also paired with its own line style (``_series_style``).
CATEGORICAL: tuple[str, ...] = (
    ACCENT,
    "#c0672c",
    "#5b3f8f",
    "#b08e24",
    "#6f6f6f",
    "#b04a63",
    "#5a8a32",
    "#3d5a80",
)

# Text in a line's own colour needs more contrast than the line: the accent and the orange are
# written in darker shades of the same hue.
LABEL_SHADES = {ACCENT: "#0b7285", "#c0672c": "#a4521d"}

# Context series beside one focal series: greys that differ in lightness and dash pattern.
CONTEXT_STYLES: tuple[tuple[str, object], ...] = (
    ("#454545", (0, (5, 2))),
    ("#6e6e69", (0, (5, 2, 1, 2))),
    ("#8f8f8a", (0, (1, 1.6))),
    ("#5f5f5a", (0, (2, 2))),
)
# Greys whose labels are printed in the secondary text colour, which reads better than a pale
# line colour.
GREYS = frozenset({NEUTRAL, NEUTRAL_LIGHT, *(colour for colour, _ in CONTEXT_STYLES)})

# Negative numbers carry a true minus sign, as in the site's text and tables.
MINUS = "\u2212"

# One-hue sequential ramp on the accent, light to dark.
SEQUENTIAL: tuple[str, ...] = ("#eef8fb", "#cdebf2", "#9fd6e5", "#5fb8cf", ACCENT, "#0c5466")

SEQUENTIAL_CMAP = LinearSegmentedColormap.from_list("accent_ramp", list(SEQUENTIAL))

# Line styles and marker shapes cycled alongside the categorical colours, so that series can
# still be told apart in greyscale or with a colour-vision deficiency. The first four series
# differ by dash pattern alone; the next four repeat the dash patterns and add a marker.
LINE_STYLES: tuple[str, ...] = ("-", "--", "-.", ":")
MARKERS: tuple[str, ...] = ("o", "s", "^", "D")

FIGURE_WIDTH = 8.0
# Point sizes of the chart text; the page shows each chart at a fixed scale of its own size, so
# these are the sizes a reader sees, multiplied by that one factor.
FONT_SIZE = 9.5
TICK_SIZE = 9.0
NOTE_SIZE = 8.5

# The title of every chart drawn since the registry was last cleared, by file stem. The site
# prints it above the figure.
TITLES: dict[str, str] = {}


def _title(path: Path, title: str) -> None:
    """Record a chart's title for the page instead of drawing it into the SVG."""
    TITLES[Path(path).stem] = title


def _wrap(text: str, width: int) -> str:
    return textwrap.fill(str(text), width=max(width, 8), break_long_words=False)


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
            # The serif the SVG embeds (``save``), so the layout here is the one a reader sees.
            "font.family": CHART_FONT,
            "font.size": FONT_SIZE,
            "text.color": TEXT_PRIMARY,
            "axes.labelcolor": TEXT_SECONDARY,
            "axes.labelsize": FONT_SIZE,
            "axes.edgecolor": AXIS,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.titlesize": FONT_SIZE,
            "axes.titleweight": "normal",
            "axes.titlecolor": TEXT_PRIMARY,
            "axes.titlelocation": "left",
            "axes.titlepad": 8,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "grid.linestyle": "-",
            "axes.axisbelow": True,
            "xtick.color": AXIS,
            "ytick.color": AXIS,
            "xtick.labelcolor": TEXT_SECONDARY,
            "ytick.labelcolor": TEXT_SECONDARY,
            "xtick.labelsize": TICK_SIZE,
            "ytick.labelsize": TICK_SIZE,
            "xtick.major.size": 3,
            "ytick.major.size": 3,
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
            "lines.linewidth": 1.8,
            "lines.solid_joinstyle": "round",
            "lines.solid_capstyle": "round",
            "legend.frameon": False,
            "legend.fontsize": TICK_SIZE,
            "legend.handlelength": 2.4,
            "svg.fonttype": "none",
            "svg.hashsalt": "dgt-stats",
            "figure.dpi": 100,
        }
    )


def save(fig: plt.Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.StringIO()
    fig.savefig(buffer, format="svg", metadata={"Date": None}, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    path.write_text(_embed_fonts(buffer.getvalue()), encoding="utf-8")
    return path


_TEXT = re.compile(r"<text\b([^>]*)>([^<]*)</text>")


def _font_data(weight: int, characters: str) -> str:
    """The chart font at ``weight``, cut to ``characters``, as a WOFF data URI."""
    options = font_subset.Options()
    options.flavor = "woff"
    options.layout_features = ["kern", "liga"]
    options.name_IDs = [1, 2]
    options.notdef_outline = True
    options.recalc_timestamp = False
    font = TTFont(CHART_FONT_FILES[weight], recalcTimestamp=False)
    subsetter = font_subset.Subsetter(options)
    subsetter.populate(text=characters)
    subsetter.subset(font)
    data = io.BytesIO()
    font_subset.save_font(font, data, options)
    return "data:font/woff;base64," + base64.b64encode(data.getvalue()).decode("ascii")


def _embed_fonts(svg: str) -> str:
    """Embed the glyphs a chart uses, by weight, and give its text a serif fallback.

    An SVG shown as an image cannot use the page's fonts, so without this the chart would be
    drawn in whatever serif the reader's system has, at widths the layout did not allow for.
    """
    by_weight: dict[int, set[str]] = {}
    for attributes, text in _TEXT.findall(svg):
        weight = HEADING_WEIGHT if "font-weight: 600" in attributes else 400
        by_weight.setdefault(weight, set()).update(html.unescape(text))
    if not by_weight:
        return svg
    # Labels laid out with two spaces keep them: SVG text collapses spaces unless told not to.
    rules = "text{white-space:pre}" + "".join(
        f"@font-face{{font-family:'{CHART_FONT}';font-weight:{weight};"
        f"src:url({_font_data(weight, ''.join(sorted(chars)))}) format('woff')}}"
        for weight, chars in sorted(by_weight.items())
    )
    svg = svg.replace(
        f"font-family: '{CHART_FONT}'", f"font-family: '{CHART_FONT}', 'Times New Roman', serif"
    )
    return svg.replace(
        '<defs>\n  <style type="text/css">', f'<defs>\n  <style type="text/css">{rules}', 1
    )


def caption(source: str, period: str, definition: str, n: str | int | None = None) -> str:
    parts = [f"Source: {source}", f"Period: {period}", f"Definition: {definition}"]
    if n is not None:
        parts.append(f"n = {n:,}" if isinstance(n, int) else f"n = {n}")
    return ". ".join(parts) + "."


def _tick(value: float, _: object = None) -> str:
    """Thousands separators, and up to two decimals only when the tick is not a whole number."""
    if float(value).is_integer():
        return f"{value:,.0f}".replace("-", MINUS)
    return f"{value:,.2f}".rstrip("0").rstrip(".").replace("-", MINUS)


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
    return f"{text}%".replace("-", MINUS)


def _percent(axis: plt.Axes, decimals: int | None = None) -> None:
    axis.yaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda v, _: _percent_text(v, decimals))
    )


def _reference_line(axis: plt.Axes, value: float, vertical: bool = False) -> None:
    """The value a comparison is read against: a dotted dark-grey line."""
    draw = axis.axvline if vertical else axis.axhline
    draw(value, color=REFERENCE, linewidth=1.1, linestyle=":", zorder=1)


def _end_labels(
    axis: plt.Axes, entries: list[tuple[float, float, str, str]], width: int = 24
) -> None:
    """Label lines at their right ends, nudging labels apart vertically so that none overlap.

    ``entries`` are ``(x, y, text, colour)`` at each line's last point. Labels are placed in
    display space, at least one line of text apart, and kept as close to their lines as that
    allows; the text is wrapped at ``width`` characters.
    """
    if not entries:
        return
    figure = axis.figure
    transform = axis.transData
    texts = [_wrap(text, width) for _, _, text, _ in entries]
    anchors = [transform.transform((x, y)) for x, y, _, _ in entries]
    line_height = TICK_SIZE * 1.25 * figure.dpi / 72
    heights = [line_height * (text.count("\n") + 1) for text in texts]
    order = sorted(range(len(entries)), key=lambda i: anchors[i][1])
    targets = {i: anchors[i][1] for i in order}
    # Relax overlapping neighbours apart, half each way, until every pair has room.
    for _ in range(200):
        moved = False
        for lower, upper in zip(order, order[1:]):
            room = (heights[lower] + heights[upper]) / 2
            gap = targets[upper] - targets[lower]
            if gap < room - 0.01:
                shift = (room - gap) / 2
                targets[lower] -= shift
                targets[upper] += shift
                moved = True
        if not moved:
            break
    inverse = transform.inverted()
    for i, (x, _, _, colour) in enumerate(entries):
        _, y = inverse.transform((anchors[i][0], targets[i]))
        axis.annotate(
            texts[i],
            (x, y),
            xytext=(7, 0),
            textcoords="offset points",
            va="center",
            ha="left",
            fontsize=TICK_SIZE,
            color=TEXT_SECONDARY if colour in GREYS else LABEL_SHADES.get(colour, colour),
            annotation_clip=False,
            # A reference line that runs under a label stops short of its text.
            bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 0.6},
        )


def _line_look(
    names: list[object], focal: object | None, colors: dict[str, str] | None
) -> dict[object, dict[str, object]]:
    """Colour, dash and width for each series: one accent among greys, or categorical."""
    looks: dict[object, dict[str, object]] = {}
    context = 0
    for index, name in enumerate(names):
        if colors and str(name) in colors:
            looks[name] = {"color": colors[str(name)], "linestyle": "-", "linewidth": 1.8}
        elif focal is not None:
            if name == focal:
                looks[name] = {"color": ACCENT, "linestyle": "-", "linewidth": 2.2}
            else:
                colour, dash = CONTEXT_STYLES[context % len(CONTEXT_STYLES)]
                looks[name] = {"color": colour, "linestyle": dash, "linewidth": 1.5}
                context += 1
        else:
            looks[name] = {"color": CATEGORICAL[index], **_series_style(index)}
    return looks


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
    focal: str | None = None,
    colors: dict[str, str] | None = None,
    linestyles: dict[str, object] | None = None,
) -> Path:
    """One or more lines on a single axis, labelled at their ends when there are up to five.

    ``focal`` names the series drawn in the accent, the others in greys; without it the series
    take the categorical colours. ``colors`` and ``linestyles`` fix a series' look by name.
    Pass ``end_labels=False`` when the series converge at the right edge (a legend is drawn
    instead) and ``band=(low_column, high_column)`` to show an interval around each line: shaded
    for one line, as thin dotted bounds for several.
    """
    apply_style()
    fig, axis = plt.subplots(figsize=(FIGURE_WIDTH, height))
    groups = [(None, frame)] if series is None else list(frame.groupby(series, sort=False))
    if len(groups) > len(CATEGORICAL):
        raise ValueError("more series than fixed colours; fold to 'Other' or facet")
    looks = _line_look([name for name, _ in groups], focal, colors)
    if series is None:
        looks = {None: {"color": ACCENT, "linestyle": "-", "linewidth": 2.0}}
    labelled = end_labels and series is not None and len(groups) <= 5
    entries = []
    for name, group in groups:
        group = group.sort_values(x)
        look = dict(looks[name])
        if linestyles and str(name) in linestyles:
            look["linestyle"] = linestyles[str(name)]
        colour = look["color"]
        if band is not None and len(groups) == 1:
            axis.fill_between(
                group[x], group[band[0]], group[band[1]], color=colour, alpha=0.13, linewidth=0
            )
        elif band is not None:
            # Several intervals are drawn as thin bounds in each line's colour: shaded, they
            # would overlap into one colour that belongs to no line.
            for bound in band:
                axis.plot(
                    group[x],
                    group[bound],
                    color=colour,
                    linewidth=0.8,
                    alpha=1.0,
                    linestyle=(0, (1, 1.6)),
                )
        axis.plot(group[x], group[y], label=None if name is None else str(name), **look)
        last = group.dropna(subset=[y]).iloc[-1] if group[y].notna().any() else None
        if last is not None:
            axis.plot(
                [last[x]],
                [last[y]],
                marker="o",
                markersize=5,
                color=colour,
                markeredgecolor=SURFACE,
                markeredgewidth=1.2,
                linestyle="none",
            )
            if labelled:
                entries.append((last[x], last[y], str(name), colour))
    if reference is not None:
        _reference_line(axis, reference)
    if zero_based:
        axis.set_ylim(bottom=0)
    if percent:
        _percent(axis)
    else:
        _thousands(axis)
    _integer_x(axis)
    _title(path, title)
    axis.set_ylabel(ylabel)
    axis.set_xlabel("")
    if labelled:
        _end_labels(axis, entries)
    elif len(groups) >= 2:
        axis.legend(loc="upper left", bbox_to_anchor=(0, -0.1), ncol=min(len(groups), 3))
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
    colors: list[str] | None = None,
) -> Path:
    """Stacked 100 % bars, one colour per series in fixed order, thin surface gaps between them."""
    apply_style()
    wide = frame.pivot_table(index=x, columns=series, values=value, aggfunc="sum").fillna(0)
    if order:
        unknown = sorted(set(map(str, wide.columns)) - set(order))
        if unknown:
            raise ValueError(f"series not in order: {unknown}")
        wide = wide.reindex(columns=[c for c in order if c in wide.columns])
    palette = list(colors) if colors else list(CATEGORICAL)
    if wide.shape[1] > len(palette):
        raise ValueError("more series than fixed colours; fold to 'Other'")
    shares = wide.div(wide.sum(axis=1), axis=0)
    fig, axis = plt.subplots(figsize=(FIGURE_WIDTH, height))
    bottom = np.zeros(len(shares))
    positions = np.arange(len(shares))
    for index, column in enumerate(shares.columns):
        values = shares[column].to_numpy()
        light = matplotlib.colors.to_rgb(palette[index])
        outlined = 0.2126 * light[0] + 0.7152 * light[1] + 0.0722 * light[2] > 0.6
        axis.bar(
            positions,
            values,
            bottom=bottom,
            width=0.72,
            color=palette[index],
            # A pale fill gets an outline, so its segment and legend key stay visible on white.
            edgecolor=NEUTRAL if outlined else SURFACE,
            linewidth=0.8 if outlined else 1.2,
            label=str(column),
        )
        bottom = bottom + values
    axis.set_xticks(positions, [str(v) for v in shares.index])
    axis.tick_params(axis="x", length=0)
    axis.set_ylim(0, 1)
    _percent(axis)
    _title(path, title)
    axis.legend(loc="upper left", bbox_to_anchor=(0, -0.08), ncol=2)
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
    axis.set_xticks(range(cols), [str(c) for c in matrix.columns], fontsize=NOTE_SIZE)
    axis.set_yticks(range(rows), [str(r) for r in matrix.index], fontsize=NOTE_SIZE)
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
                    fontsize=NOTE_SIZE,
                    color=SURFACE if cell >= threshold else TEXT_PRIMARY,
                )
    bar = fig.colorbar(image, ax=axis, fraction=0.03, pad=0.02)
    bar.outline.set_visible(False)
    bar.ax.tick_params(length=0)
    if percent:
        # One decimal on every tick as soon as one tick is not a whole percentage, otherwise a
        # bar with ticks every half point would print the same label three times.
        whole = all(round(float(t) * 100, 6).is_integer() for t in bar.get_ticks())
        decimals = 0 if whole else 1
        bar.formatter = matplotlib.ticker.FuncFormatter(lambda v, _: _percent_text(v, decimals))
    else:
        bar.formatter = matplotlib.ticker.FuncFormatter(_tick)
    bar.update_ticks()
    _title(path, title)
    axis.set_xlabel(xlabel)
    axis.set_ylabel(ylabel)
    return save(fig, path)


# How each kind of row is drawn in a dot-and-interval chart: the estimate a chart is about, a
# comparison (a descriptive table), a baseline with nothing to estimate, the reference row the
# others are measured against, and a pooled or adjusted summary.
DOT_STYLES: dict[str, dict[str, object]] = {
    "focal": {
        "marker": "o",
        "size": 6.5,
        "face": ACCENT,
        "edge": SURFACE,
        "line": ACCENT,
        "alpha": 0.8,
    },
    "context": {
        "marker": "s",
        "size": 5.5,
        "face": NEUTRAL,
        "edge": SURFACE,
        "line": NEUTRAL,
        "alpha": 0.8,
    },
    "baseline": {
        "marker": "o",
        "size": 5.5,
        "face": SURFACE,
        "edge": NEUTRAL,
        "line": NEUTRAL_LIGHT,
        "alpha": 1.0,
    },
    "reference": {
        "marker": "o",
        "size": 6.0,
        "face": SURFACE,
        "edge": NEUTRAL,
        "line": NEUTRAL,
        "alpha": 0.9,
    },
    "summary": {
        "marker": "D",
        "size": 6.0,
        "face": TEXT_PRIMARY,
        "edge": SURFACE,
        "line": TEXT_PRIMARY,
        "alpha": 0.9,
    },
}


def _dots(axis: plt.Axes, xs, ys, lows, highs, kind: str) -> None:
    look = DOT_STYLES[kind]
    axis.hlines(ys, lows, highs, color=look["line"], linewidth=1.6, alpha=look["alpha"], zorder=2)
    axis.plot(
        xs,
        ys,
        marker=look["marker"],
        markersize=look["size"],
        markerfacecolor=look["face"],
        markeredgecolor=look["edge"] if look["face"] != SURFACE else look["edge"],
        markeredgewidth=1.0 if look["face"] != SURFACE else 1.4,
        linestyle="none",
        zorder=3,
    )


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
    reference_row: str | None = None,
    style: str | None = None,
    group: str | None = None,
    xlim: tuple[float, float] | None = None,
) -> Path:
    """Dots with interval whiskers, one row per label, highest value at the top.

    ``keep_order`` keeps the frame's own order (first row at the top) instead of ranking.
    ``highlight`` names a boolean column: its rows are drawn as filled accent dots and the
    others as hollow grey ones, for a true estimate among placebos. ``reference_row`` names the
    row the others are compared with, drawn hollow and grey and labelled as the reference.
    ``style`` names a column giving each row's kind (a key of ``DOT_STYLES``), and ``group`` a
    column whose values head blocks of rows (implies ``keep_order``). ``xlim`` fixes the value
    axis; a row whose value lies beyond its right end is written out at that end instead.
    """
    apply_style()
    if keep_order or group is not None:
        ordered = frame.reset_index(drop=True)
    else:
        ordered = frame.sort_values(value, ascending=False).reset_index(drop=True)
    kinds = []
    for _, row in ordered.iterrows():
        if style is not None:
            kinds.append(str(row[style]))
        elif reference_row is not None and str(row[label]) == reference_row:
            kinds.append("reference")
        elif highlight is not None:
            kinds.append("focal" if bool(row[highlight]) else "reference")
        else:
            kinds.append("focal")
    # Rows top to bottom, with a heading row before each group.
    rows: list[tuple[str, int | None]] = []
    previous = object()
    for index, row in ordered.iterrows():
        if group is not None and row[group] != previous:
            rows.append((str(row[group]), None))
            previous = row[group]
        text = str(row[label])
        if kinds[index] == "reference" and reference_row is not None:
            text += " (reference)"
        rows.append((text, index))
    height = max(2.4, 0.27 * len(rows) + 1.0)
    fig, axis = plt.subplots(figsize=(FIGURE_WIDTH, height))
    positions = np.arange(len(rows))[::-1]
    for kind in DOT_STYLES:
        picked = [
            (pos, i) for pos, (_, i) in zip(positions, rows) if i is not None and kinds[i] == kind
        ]
        if not picked:
            continue
        ys = [pos for pos, _ in picked]
        idx = [i for _, i in picked]
        _dots(
            axis,
            ordered.loc[idx, value],
            ys,
            ordered.loc[idx, low],
            ordered.loc[idx, high],
            kind,
        )
    if reference is not None:
        _reference_line(axis, reference, vertical=True)
        if reference_label:
            axis.annotate(
                reference_label,
                (reference, len(rows) - 0.55),
                xytext=(4, 0),
                textcoords="offset points",
                fontsize=NOTE_SIZE,
                color=TEXT_SECONDARY,
                va="center",
            )
    axis.set_yticks(positions, [text for text, _ in rows], fontsize=TICK_SIZE)
    for tick, (_, i) in zip(axis.get_yticklabels(), rows):
        if i is None:
            tick.set_fontweight(HEADING_WEIGHT)
            tick.set_color(TEXT_PRIMARY)
    axis.tick_params(axis="y", length=0)
    axis.spines["left"].set_visible(False)
    axis.grid(True, axis="x")
    axis.grid(False, axis="y")
    if xlim is not None:
        axis.set_xlim(*xlim)
        for pos, (_, i) in zip(positions, rows):
            if i is None or float(ordered.loc[i, value]) <= xlim[1]:
                continue
            shown = (
                _percent_text(float(ordered.loc[i, value]), 1)
                if percent
                else _tick(float(ordered.loc[i, value]))
            )
            # The value is written out, with a short arrow to the axis end it lies beyond.
            axis.annotate(
                shown,
                (xlim[1], pos),
                xytext=(-22, 0),
                textcoords="offset points",
                ha="right",
                va="center",
                fontsize=NOTE_SIZE,
                color=TEXT_PRIMARY,
                arrowprops={"arrowstyle": "->", "color": TEXT_PRIMARY, "lw": 0.8, "shrinkA": 3},
            )
    elif float(ordered[low].min()) >= -1e-9:
        axis.set_xlim(left=0)
    if percent:
        # Changes carry a sign; shares do not (an interval may end a rounding error below 0).
        signed = float(ordered[low].min()) < -1e-9
        axis.xaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(lambda v, _: _percent_text(v, signed=signed))
        )
    axis.set_ylim(-0.7, len(rows) - 0.3)
    _title(path, title)
    axis.set_xlabel(xlabel)
    return save(fig, path)


def dot_range(
    frame: pd.DataFrame,
    label: str,
    value: str,
    low: str,
    high: str,
    alternative: str,
    path: Path,
    title: str,
    xlabel: str = "",
    value_label: str = "",
    alternative_label: str = "",
    log: bool = False,
    reference: float | None = None,
    reference_label: str = "",
) -> Path:
    """One row per label (first row at the top): an estimate with its interval, and the same
    quantity under an alternative assumption joined to it by a broad grey band.

    The band is a sensitivity range, not an interval, so it is drawn differently from the
    whisker: broad, light and behind, with a hollow grey diamond at the alternative value. Rows
    where the two agree show no band. The legend names the three marks.
    """
    apply_style()
    ordered = frame.reset_index(drop=True)
    height = max(2.6, 0.36 * len(ordered) + 1.5)
    fig, axis = plt.subplots(figsize=(FIGURE_WIDTH, height))
    positions = np.arange(len(ordered))[::-1]
    for position, (_, row) in zip(positions, ordered.iterrows()):
        a, b = float(row[value]), float(row[alternative])
        if not np.isclose(a, b, rtol=1e-6):
            axis.hlines(
                position,
                min(a, b),
                max(a, b),
                color=NEUTRAL_LIGHT,
                linewidth=8,
                alpha=0.6,
                capstyle="butt",
                zorder=1,
            )
            axis.plot(
                [b],
                [position],
                marker="D",
                markersize=6,
                markerfacecolor=SURFACE,
                markeredgecolor=NEUTRAL,
                markeredgewidth=1.4,
                linestyle="none",
                zorder=3,
            )
    _dots(axis, ordered[value], positions, ordered[low], ordered[high], "focal")
    if reference is not None:
        _reference_line(axis, reference, vertical=True)
        if reference_label:
            axis.annotate(
                reference_label,
                (reference, len(ordered) - 0.55),
                xytext=(4, 0),
                textcoords="offset points",
                fontsize=NOTE_SIZE,
                color=TEXT_SECONDARY,
                va="center",
            )
    if log:
        axis.set_xscale("log")
        axis.xaxis.set_major_locator(
            matplotlib.ticker.FixedLocator([100, 200, 300, 500, 1000, 2000, 3000, 5000])
        )
        axis.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
        axis.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(_tick))
    axis.set_yticks(positions, [str(v) for v in ordered[label]], fontsize=TICK_SIZE)
    axis.tick_params(axis="y", length=0)
    axis.spines["left"].set_visible(False)
    axis.grid(True, axis="x")
    axis.grid(False, axis="y")
    axis.set_ylim(-0.7, len(ordered) - 0.3)
    handles = [
        matplotlib.lines.Line2D(
            [],
            [],
            color=ACCENT,
            marker="o",
            markersize=6.5,
            markeredgecolor=SURFACE,
            linewidth=1.6,
            label=value_label,
        ),
        matplotlib.lines.Line2D(
            [],
            [],
            color=NEUTRAL,
            marker="D",
            markersize=6,
            markerfacecolor=SURFACE,
            markeredgewidth=1.4,
            linestyle="none",
            label=alternative_label,
        ),
        matplotlib.lines.Line2D(
            [], [], color=NEUTRAL_LIGHT, linewidth=8, alpha=0.6, label="Range between the two"
        ),
    ]
    axis.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, -0.16), ncol=1)
    _title(path, title)
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
            _dots(axis, [1.0], [position], [1.0], [1.0], "reference")
            continue
        _dots(axis, [row[value]], [position], [row[low]], [row[high]], "focal")
    _reference_line(axis, 1.0, vertical=True)
    axis.set_xscale("log")
    axis.set_yticks(positions, tick_labels, fontsize=NOTE_SIZE)
    for tick, (_, row) in zip(axis.get_yticklabels(), rows):
        if row is None:
            tick.set_fontweight(HEADING_WEIGHT)
            tick.set_color(TEXT_PRIMARY)
    axis.tick_params(axis="y", length=0)
    axis.spines["left"].set_visible(False)
    # Labelled ticks at each doubling either side of 1; the default log locator labels only the
    # powers of ten, which leaves everything between 1 and 10 without a number.
    axis.xaxis.set_major_locator(matplotlib.ticker.FixedLocator([0.1, 0.25, 0.5, 1, 2, 4, 8]))
    axis.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    axis.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    axis.grid(True, axis="x")
    axis.grid(False, axis="y")
    axis.set_ylim(-0.7, len(rows) - 0.3)
    _title(path, title)
    axis.set_xlabel(xlabel)
    return save(fig, path)


def calibration(
    frame: pd.DataFrame,
    predicted: str,
    observed: str,
    path: Path,
    title: str,
    series: str | None = None,
    xlabel: str = "Mean predicted probability in the decile",
) -> Path:
    """Observed share against mean predicted probability by bin (deciles by default), with the
    diagonal on which the two are equal."""
    apply_style()
    fig, axis = plt.subplots(figsize=(FIGURE_WIDTH, 4.8))
    groups = [(None, frame)] if series is None else list(frame.groupby(series, sort=False))
    top = 0.0
    for index, (name, group) in enumerate(groups):
        group = group.sort_values(predicted)
        axis.plot(
            group[predicted],
            group[observed],
            marker=MARKERS[index % len(MARKERS)],
            markersize=6.5,
            linestyle=LINE_STYLES[index % len(LINE_STYLES)],
            linewidth=1.6,
            color=CATEGORICAL[index],
            markeredgecolor=SURFACE,
            markeredgewidth=1,
            label=None if name is None else str(name),
        )
        top = max(top, float(group[[predicted, observed]].max().max()))
    limit = top * 1.05
    axis.plot([0, limit], [0, limit], color=REFERENCE, linewidth=1.1, linestyle=":", zorder=1)
    axis.annotate(
        "predicted = observed",
        (limit * 0.97, limit * 0.97),
        ha="right",
        va="bottom",
        fontsize=NOTE_SIZE,
        color=TEXT_SECONDARY,
        rotation=0,
    )
    axis.set_xlim(-0.015 * limit, limit)
    axis.set_ylim(-0.015 * limit, limit)
    axis.grid(True, axis="both")
    _percent(axis, 1)
    axis.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v * 100:.1f}%"))
    _title(path, title)
    axis.set_xlabel(xlabel)
    axis.set_ylabel("Observed share")
    # Each series is named at its last point, to the left of it near the top right corner.
    for index, (name, group) in enumerate(groups):
        if name is None:
            continue
        last = group.sort_values(predicted).iloc[-1]
        right = float(last[predicted]) > 0.6 * limit
        axis.annotate(
            str(name),
            (float(last[predicted]), float(last[observed])),
            xytext=(-9, 3) if right else (9, -3),
            textcoords="offset points",
            ha="right" if right else "left",
            va="bottom" if right else "top",
            fontsize=TICK_SIZE,
            color=LABEL_SHADES.get(CATEGORICAL[index], CATEGORICAL[index]),
            bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 0.6},
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


def _panel_title(axis: plt.Axes, text: str, panels: int) -> None:
    """A small-multiple panel's title, wrapped to the panel's width so neighbours never collide."""
    width = int(FIGURE_WIDTH * 72 / max(panels, 1) / (FONT_SIZE * 0.56))
    axis.set_title(_wrap(text, width), fontsize=FONT_SIZE, loc="left")


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
    reference: float | None = None,
    from_zero: bool = True,
    shared: bool = False,
) -> Path:
    """Side-by-side dot-and-whisker panels sharing one row order (``order``, top to bottom).

    Each panel has its own x scale, from zero unless ``from_zero`` is False (ratios read against
    ``reference``), so the panels compare rankings, not magnitudes; with ``shared`` every panel
    has the same scale and ticks, for panels of one measure. ``reference`` draws the same dotted
    vertical line on every panel, the null value a ratio is read against, and is always inside
    the scale. A row a panel has no value for says so. The axis label is written once, under
    the middle panel.
    """
    apply_style()
    labels_order = order or list(dict.fromkeys(frame[label]))
    panels = panel_order or list(dict.fromkeys(frame[panel]))
    height = max(2.8, 0.34 * len(labels_order) + 1.6)
    fig, axes = plt.subplots(
        1,
        len(panels),
        figsize=(FIGURE_WIDTH, height),
        sharey=True,
        sharex=shared,
        constrained_layout=True,
    )
    axes = np.atleast_1d(axes)
    positions = np.arange(len(labels_order))[::-1]
    for axis, name in zip(axes, panels):
        block = frame[frame[panel] == name].set_index(label).reindex(labels_order)
        _dots(axis, block[value], positions, block[low], block[high], "focal")
        for pos, missing in zip(positions, block[value].isna()):
            if missing:
                axis.annotate(
                    "not available",
                    (0.03, pos),
                    xycoords=("axes fraction", "data"),
                    bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 0.6},
                    zorder=3,
                    va="center",
                    fontsize=NOTE_SIZE,
                    color=TEXT_SECONDARY,
                )
        _panel_title(axis, str(name), len(panels))
        axis.grid(True, axis="x")
        axis.grid(False, axis="y")
        axis.spines["left"].set_visible(False)
        axis.tick_params(axis="y", length=0)
        if from_zero:
            axis.set_xlim(left=0)
        if reference is not None and not shared:
            left, right = axis.get_xlim()
            pad = 0.05 * (right - left)
            axis.set_xlim(min(left, reference - pad), max(right, reference + pad))
        axis.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(_tick))
        axis.xaxis.set_major_locator(
            matplotlib.ticker.MaxNLocator(nbins=4, steps=[1, 2, 2.5, 5, 10])
        )
        axis.tick_params(labelsize=NOTE_SIZE)
        if reference is not None:
            _reference_line(axis, reference, vertical=True)
    if shared:
        # One scale for every panel, set once all of them are drawn.
        left = 0.0 if from_zero else float(frame[low].min())
        right = float(frame[high].max())
        if reference is not None:
            left, right = min(left, reference), max(right, reference)
        pad = 0.05 * (right - left)
        axes[0].set_xlim(left if from_zero else left - pad, right + pad)
    if xlabel:
        fig.supxlabel(xlabel, fontsize=NOTE_SIZE, color=TEXT_SECONDARY)
    axes[0].set_yticks(positions, [str(v) for v in labels_order], fontsize=TICK_SIZE)
    axes[0].set_ylim(-0.7, len(labels_order) - 0.3)
    _title(path, title)
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
    highlight: list[str] | None = None,
) -> Path:
    """Two ranked columns joined by a line per row: how each label moves between two measures.

    Rows are placed by rank on each side (highest value at the top); the values are printed next to
    the labels so the reader has the numbers, not only the order. ``highlight`` names the rows
    drawn in the accent; the others are grey.
    """
    apply_style()
    n = len(frame)
    left_rank = frame[left].rank(ascending=False, method="first")
    right_rank = frame[right].rank(ascending=False, method="first")
    picked = set(highlight or [])
    fig, axis = plt.subplots(figsize=(FIGURE_WIDTH, max(3.0, 0.42 * n + 1.4)))
    for index, (_, row) in enumerate(frame.iterrows()):
        y0, y1 = n - left_rank.iloc[index], n - right_rank.iloc[index]
        focal = str(row[label]) in picked
        colour = ACCENT if focal else NEUTRAL_LIGHT
        text_colour = TEXT_PRIMARY if focal or not picked else TEXT_SECONDARY
        axis.plot(
            [0, 1],
            [y0, y1],
            color=colour,
            linewidth=2.2 if focal else 1.6,
            marker="o",
            markersize=6 if focal else 5,
            zorder=3 if focal else 2,
        )
        weight = HEADING_WEIGHT if focal else "normal"
        axis.text(
            -0.04,
            y0,
            f"{row[label]}  {value_format.format(row[left])}",
            ha="right",
            va="center",
            fontsize=TICK_SIZE,
            color=text_colour,
            fontweight=weight,
        )
        axis.text(
            1.04,
            y1,
            f"{value_format.format(row[right])}  {row[label]}",
            ha="left",
            va="center",
            fontsize=TICK_SIZE,
            color=text_colour,
            fontweight=weight,
        )
    axis.text(
        0, n - 0.2, left_title, ha="center", va="bottom", fontsize=TICK_SIZE, color=TEXT_SECONDARY
    )
    axis.text(
        1, n - 0.2, right_title, ha="center", va="bottom", fontsize=TICK_SIZE, color=TEXT_SECONDARY
    )
    axis.set_xlim(-0.9, 1.9)
    axis.set_ylim(-0.6, n + 0.4)
    axis.axis("off")
    _title(path, title)
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
    alternative: tuple[str, str] | None = None,
) -> Path:
    """Observed monthly counts, the fitted line and the dashed counterfactual around a break.

    One panel, or one panel per ``facet`` value stacked with shared x and y axes, so that the
    groups a difference-in-differences design compares sit on one vertical scale. ``shaded``
    marks periods (for example a confounding change or the pandemic) with a labelled grey band.
    ``alternative`` is ``(column, label)`` for a second counterfactual drawn dotted beside the
    first, which is how two trend specifications are compared on one picture.
    """
    apply_style()
    facets = [None] if facet is None else (facet_order or list(dict.fromkeys(frame[facet])))
    height = height or (3.8 if facet is None else 2.6 * len(facets) + 0.8)
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
            color=NEUTRAL,
            linewidth=0.9,
            marker="o",
            markersize=2.6,
            label="Observed",
        )
        axis.plot(panel[x], panel[fitted], color=ACCENT, linewidth=2, label="Fitted")
        post = panel[panel[x] >= break_date]
        axis.plot(
            post[x],
            post[counterfactual],
            color=TEXT_PRIMARY,
            linewidth=1.7,
            linestyle=(0, (5, 2)),
            label="Counterfactual (no change)",
        )
        if alternative is not None:
            column, alt_label = alternative
            axis.plot(
                post[x],
                post[column],
                color=NEUTRAL,
                linewidth=1.7,
                linestyle=(0, (1, 1.4)),
                label=alt_label,
            )
        axis.axvline(break_date, color=TEXT_PRIMARY, linewidth=0.9)
        for start, end, _ in shaded or []:
            axis.axvspan(start, end, color=GRID, alpha=0.8, linewidth=0)
        axis.set_ylim(bottom=0)
        _thousands(axis)
        axis.set_ylabel(ylabel)
        if name is not None:
            _panel_title(axis, str(name), 1)
    # Period labels go in once every panel is drawn, so they hang from the final (shared) top,
    # one step below the break label so the two never run into each other.
    for axis in axes:
        top = axis.get_ylim()[1]
        for index, (start, _, label) in enumerate(shaded or []):
            axis.text(
                start,
                top * (0.86 - 0.12 * index),  # stagger neighbouring labels
                f" {label}",
                fontsize=NOTE_SIZE,
                color=TEXT_SECONDARY,
                va="top",
            )
    axes[0].annotate(
        break_label,
        (break_date, axes[0].get_ylim()[1] * 0.98),
        xytext=(4, 0),
        textcoords="offset points",
        fontsize=NOTE_SIZE,
        color=TEXT_PRIMARY,
        va="top",
    )
    axes[-1].legend(
        loc="upper left", bbox_to_anchor=(0, -0.12), ncol=3 if alternative is None else 2
    )
    _title(path, title)
    fig.tight_layout()
    return save(fig, path)


def trend_projection(
    frame: pd.DataFrame,
    facet: str,
    x: str,
    observed: str,
    expected: str,
    low: str,
    high: str,
    path: Path,
    title: str,
    last_fitted: int,
    order: list[str] | None = None,
    ylabel: str = "",
) -> Path:
    """Observed counts against a fitted trend and its projection, one panel per facet.

    The trend is solid up to ``last_fitted`` and dashed after it, with the prediction interval
    shaded only over the projected years; a thin vertical rule marks where fitting stopped. All
    panels share one y scale, because every facet is expressed in the same unit.
    """
    apply_style()
    facets = order or list(dict.fromkeys(frame[facet]))
    fig, axes = plt.subplots(
        1,
        len(facets),
        figsize=(FIGURE_WIDTH, 3.6),
        sharey=True,
        sharex=True,
        constrained_layout=True,
    )
    axes = np.atleast_1d(axes)
    for axis, name in zip(axes, facets):
        panel = frame[frame[facet] == name].sort_values(x)
        fitted = panel[panel[x] <= last_fitted]
        projected = panel[panel[x] >= last_fitted]
        after = panel[panel[x] > last_fitted]
        axis.fill_between(after[x], after[low], after[high], color=ACCENT, alpha=0.13, linewidth=0)
        axis.plot(fitted[x], fitted[expected], color=ACCENT, linewidth=2, label="Trend")
        axis.plot(
            projected[x],
            projected[expected],
            color=ACCENT,
            linewidth=1.8,
            linestyle=(0, (4, 2)),
            label="Trend projected",
        )
        axis.plot(
            panel[x],
            panel[observed],
            color=TEXT_PRIMARY,
            linewidth=0,
            marker="o",
            markersize=3.2,
            label="Observed",
        )
        axis.axvline(last_fitted + 0.5, color=AXIS, linewidth=0.9, linestyle=":")
        _panel_title(axis, str(name), len(facets))
        axis.set_ylim(bottom=0)
        _thousands(axis)
        _integer_x(axis, nbins=4)
        axis.tick_params(labelsize=NOTE_SIZE)
    axes[0].set_ylabel(ylabel)
    axes[0].legend(loc="lower left", fontsize=NOTE_SIZE)
    _title(path, title)
    return save(fig, path)


MONTH_TICKS = ("J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D")


def month_lines(
    frame: pd.DataFrame,
    series: str,
    value: str,
    path: Path,
    title: str,
    order: list[str] | None = None,
    reference: float | None = None,
    percent: bool = False,
    ylabel: str = "",
    zero_based: bool = False,
    focal: str | None = None,
) -> Path:
    """One line per series across the twelve months (``month`` column, 1–12), on one axis.

    Used for seasonal indices, where ``reference`` (100 for an index, 0 for a change) is the
    average month, and for month-by-month changes. With ``focal`` that series is drawn in the
    accent and the others in greys, each labelled at its December end; otherwise the series
    take the categorical colours and a legend.
    """
    apply_style()
    names = order or list(dict.fromkeys(frame[series]))
    if len(names) > len(CATEGORICAL):
        raise ValueError("more series than fixed colours; fold to 'Other' or facet")
    looks = _line_look(names, focal, None)
    fig, axis = plt.subplots(figsize=(FIGURE_WIDTH, 3.9))
    entries = []
    for name in names:
        group = frame[frame[series] == name].sort_values("month")
        look = dict(looks[name])
        look.pop("marker", None)
        look.pop("markersize", None)
        axis.plot(
            group["month"],
            group[value],
            label=str(name),
            marker="o",
            markersize=3.5 if name == focal or focal is None else 2.8,
            **look,
        )
        last = group.iloc[-1]
        entries.append((last["month"], last[value], str(name), look["color"]))
    if reference is not None:
        _reference_line(axis, reference)
    if zero_based:
        axis.set_ylim(bottom=0)
    if percent:
        signed = float(frame[value].min()) < 0
        axis.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(lambda v, _: _percent_text(v, signed=signed))
        )
    axis.set_xticks(range(1, 13), MONTH_TICKS)
    axis.set_xlim(0.6, 12.4)
    _title(path, title)
    axis.set_ylabel(ylabel)
    if focal is not None:
        _end_labels(axis, entries, width=20)
    else:
        axis.legend(loc="upper left", bbox_to_anchor=(0, -0.1), ncol=min(len(names), 2))
    return save(fig, path)


def segmented_small_multiples(
    frame: pd.DataFrame,
    facet: str,
    x: str,
    y: str,
    series: str,
    segment: str,
    path: Path,
    title: str,
    order: list[str] | None = None,
    series_order: list[str] | None = None,
    ncols: int = 3,
) -> Path:
    """Small multiples of shares whose lines break wherever ``segment`` changes.

    Each (series, segment) run is drawn as its own line in the series colour, so a recording
    break shows as a gap: the eye is not invited to read a trend across it. Each panel has its
    own percentage scale from zero.
    """
    apply_style()
    facets = order or list(dict.fromkeys(frame[facet]))
    names = series_order or list(dict.fromkeys(frame[series]))
    nrows = int(np.ceil(len(facets) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(FIGURE_WIDTH, 2.4 * nrows + 0.7), sharex=True)
    axes = np.atleast_1d(axes).ravel()
    for index, facet_name in enumerate(facets):
        axis = axes[index]
        panel = frame[frame[facet] == facet_name]
        for colour_index, name in enumerate(names):
            group = panel[panel[series] == name]
            for run_index, (_, run) in enumerate(group.groupby(segment, sort=True)):
                run = run.sort_values(x)
                axis.plot(
                    run[x],
                    run[y],
                    color=CATEGORICAL[colour_index],
                    marker="o",
                    markersize=3,
                    linewidth=1.6,
                    label=str(name) if run_index == 0 else None,
                    **{k: v for k, v in _series_style(colour_index).items() if k == "linestyle"},
                )
        _panel_title(axis, str(facet_name), ncols)
        axis.set_ylim(bottom=0)
        _percent(axis)
        _integer_x(axis, nbins=4)
        axis.tick_params(labelsize=NOTE_SIZE)
    for axis in axes[len(facets) :]:
        axis.set_visible(False)
    for index in range(len(facets)):
        if index + ncols >= len(facets):
            axes[index].tick_params(labelbottom=True)
    _title(path, title)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower left", bbox_to_anchor=(0.01, 0.0), ncol=len(names))
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    return save(fig, path)
