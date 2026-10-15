"""Render an 8–9 day activity summary as a PDF with ReportLab.

Every number comes from an AnalyticsSummary computed from persisted data. No LLM is
involved and nothing is inferred beyond the documented rules.
"""

import io
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.analytics.config import AnalyticsConfig
from app.analytics.schemas import AnalyticsSummary

INK = colors.HexColor("#1d1b16")
MUTED = colors.HexColor("#55514a")
RULE = colors.HexColor("#d6d2c4")
SOFT = colors.HexColor("#efede6")
NOTICE = colors.HexColor("#fdf0d5")
BAR = colors.HexColor("#5a6b7d")  # single neutral colour: no good/bad colouring


@dataclass(frozen=True)
class ObservationLine:
    observed_at: datetime
    category: str
    status: str
    source: str
    note: str


@dataclass(frozen=True)
class ReportInput:
    report_id: str
    patient_name: str
    summary: AnalyticsSummary
    observations: list[ObservationLine]
    config: AnalyticsConfig
    generated_at: datetime


# ---------------------------------------------------------------- fonts


_FONT_CACHE: dict[str, tuple[str, str]] = {}


def _fonts(font_path: Path | None) -> tuple[str, str]:
    """Regular/bold font names. A TTF (e.g. Noto Sans) is needed for Indic scripts."""
    if font_path is None:
        return "Helvetica", "Helvetica-Bold"
    key = str(font_path)
    if key not in _FONT_CACHE:
        pdfmetrics.registerFont(TTFont("SnehaFont", key))
        _FONT_CACHE[key] = ("SnehaFont", "SnehaFont")
    return _FONT_CACHE[key]


def _safe(text: str, unicode_font: bool) -> str:
    """Escape for ReportLab markup; without a Unicode font, replace unsupported characters."""
    if not unicode_font:
        text = text.encode("cp1252", errors="replace").decode("cp1252")
    return escape(text)


# ---------------------------------------------------------------- formatting


def _pct(value: float | None) -> str:
    return "–" if value is None else f"{value:.0%}"


def _num(value: float | None, digits: int = 2) -> str:
    return "–" if value is None else f"{value:.{digits}f}"


def _secs(ms: float | None) -> str:
    return "–" if ms is None else f"{ms / 1000:.1f} s"


def _mins(value: float | None) -> str:
    return "–" if value is None else f"{value:.0f} min"


def _day(d: date) -> str:
    return f"{d.day} {d:%b %Y}"


# ---------------------------------------------------------------- document


def build_pdf(data: ReportInput, *, font_path: Path | None = None, compress: bool = True) -> bytes:
    regular, bold = _fonts(font_path)
    uni = font_path is not None
    s = data.summary
    tz = ZoneInfo(s.timezone)

    base = getSampleStyleSheet()
    body = ParagraphStyle(
        "body",
        parent=base["BodyText"],
        fontName=regular,
        fontSize=10,
        leading=14,
        textColor=INK,
        alignment=TA_LEFT,
    )
    small = ParagraphStyle("small", parent=body, fontSize=8.5, leading=11, textColor=MUTED)
    h1 = ParagraphStyle(
        "h1",
        parent=base["Title"],
        fontName=bold,
        fontSize=18,
        leading=22,
        textColor=INK,
        alignment=TA_LEFT,
        spaceAfter=4,
    )
    h2 = ParagraphStyle(
        "h2",
        parent=base["Heading2"],
        fontName=bold,
        fontSize=12.5,
        leading=16,
        textColor=INK,
        spaceBefore=10,
        spaceAfter=4,
    )
    cell = ParagraphStyle("cell", parent=body, fontSize=9, leading=11.5)
    head = ParagraphStyle("head", parent=cell, fontName=bold)

    def p(text: str, style: ParagraphStyle = body) -> Paragraph:
        return Paragraph(_safe(text, uni), style)

    def table(rows: list[list[str]], widths: list[float]) -> Table:
        cells = [
            [Paragraph(_safe(c, uni), head if i == 0 else cell) for c in row]
            for i, row in enumerate(rows)
        ]
        t = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), SOFT),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return t

    def notice(lines: list[str]) -> Table:
        t = Table([[[p(line) for line in lines]]], colWidths=[170 * mm], hAlign="LEFT")
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), NOTICE),
                    ("BOX", (0, 0), (-1, -1), 0.6, RULE),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return t

    days_total = (s.to_date - s.from_date).days + 1
    story: list = [
        p("SNEHA activity summary", h1),
        p(f"For: {data.patient_name}"),
        p(
            f"Reporting period: {_day(s.from_date)} – {_day(s.to_date)} "
            f"({days_total} days, {s.timezone})"
        ),
        p(
            f"Generated {data.generated_at.astimezone(tz):%d %b %Y %H:%M} ({s.timezone}) · "
            f"Report {data.report_id} · Method {s.method_version}, settings {s.config_version}",
            small,
        ),
        Spacer(1, 6),
        notice(["Important: " + s.disclaimer]),
    ]

    # Data completeness and missing-data warnings
    c = s.completeness
    story += [p("Data completeness", h2)]
    story.append(
        p(
            f"Activity was recorded on {c.days_with_activity} of {c.days_elapsed} elapsed days"
            + (f" ({_pct(c.completeness_ratio)})." if c.completeness_ratio is not None else ".")
        )
    )
    if c.days_elapsed < days_total:
        story.append(
            p(
                f"The period is not over yet: {days_total - c.days_elapsed} future day(s) "
                "are not counted.",
                small,
            )
        )
    warnings = []
    if s.totals.results == 0:
        warnings.append(
            "No activity was recorded in this period, so no activity measures are shown."
        )
    if c.missing_days:
        warnings.append(
            "Days without any activity: "
            + ", ".join(_day(d) for d in c.missing_days)
            + f" (longest gap {c.longest_gap_days} days). "
            "Missing days are not counted as low performance."
        )
    if s.baseline.status != "compared":
        warnings.append(
            "Not enough earlier activity to compare with this person's usual pattern "
            f"(needs {s.baseline.required_results} results on {s.baseline.required_days} days in "
            f"the {(s.baseline.to_date - s.baseline.from_date).days + 1} days before; found "
            f"{s.baseline.results} on {s.baseline.days})."
        )
    if warnings:
        story.append(notice(["Missing-data warnings:"] + [f"• {w}" for w in warnings]))

    # Summary metrics
    t = s.totals
    e = s.engagement
    story += [
        p("Summary", h2),
        table(
            [
                ["Measure", "This period"],
                ["Activities done", str(t.results)],
                [
                    "Sessions (completed / stopped early)",
                    f"{t.sessions_started} ({t.sessions_completed} / {t.sessions_stopped})",
                ],
                ["Session completion rate", _pct(t.completion_rate)],
                [
                    "Activities stopped part-way",
                    f"{t.interrupted_results} ({_pct(t.interruption_rate)})",
                ],
                ["Sessions ended because of tiredness", str(t.sessions_ended_for_fatigue)],
                ["Average score (scored activities only)", _num(t.accuracy_mean)],
                ["Typical response time (median)", _secs(t.median_response_ms)],
                ["Hints per activity", _num(t.hints_per_result, 1)],
                ["Typical session length (median)", _mins(t.median_session_minutes)],
                [
                    "Enjoyment answers (enjoyed / neutral / not enjoyed / no answer)",
                    f"{e.enjoyed} / {e.neutral} / {e.not_enjoyed} / {e.unanswered}",
                ],
            ],
            [110 * mm, 60 * mm],
        ),
    ]

    # Activities and preferences
    if s.activities:
        story += [
            p("Activities", h2),
            table(
                [
                    [
                        "Activity",
                        "Done",
                        "Stopped",
                        "Avg score",
                        "Response",
                        "Hints",
                        "Level",
                        "Enjoyed",
                    ]
                ]
                + [
                    [
                        a.title,
                        str(a.results),
                        str(a.interrupted),
                        _num(a.accuracy_mean),
                        _secs(a.median_response_ms),
                        _num(a.hints_per_result, 1),
                        _num(a.mean_difficulty, 1),
                        f"{a.enjoyed}/{a.enjoyed + a.not_enjoyed}",
                    ]
                    for a in s.activities
                ],
                [46 * mm, 15 * mm, 17 * mm, 19 * mm, 20 * mm, 15 * mm, 15 * mm, 18 * mm],
            ),
        ]
        top = [pr.title for pr in s.preferences[:3]]
        story.append(p("Most enjoyed or most chosen: " + ", ".join(top) + ".", small))

    # Daily trend
    story += [p("Day by day", h2)]
    chart_days = s.daily
    if chart_days:
        drawing = Drawing(170 * mm, 45 * mm)
        chart = VerticalBarChart()
        chart.x, chart.y, chart.width, chart.height = 10 * mm, 8 * mm, 155 * mm, 32 * mm
        chart.data = [[d.results for d in chart_days]]
        chart.categoryAxis.categoryNames = [f"{d.day:%d %b}" for d in chart_days]
        chart.categoryAxis.labels.fontName = regular
        chart.categoryAxis.labels.fontSize = 7
        chart.valueAxis.valueMin = 0
        chart.valueAxis.labels.fontName = regular
        chart.valueAxis.labels.fontSize = 7
        chart.bars[0].fillColor = BAR
        chart.bars[0].strokeColor = None
        drawing.add(chart)
        story += [drawing, p("Activities per day.", small)]
    story.append(
        table(
            [["Day", "Activities", "Stopped", "Avg score", "Response", "Hints"]]
            + [
                [
                    _day(d.day),
                    str(d.results) if d.has_data else "no data",
                    str(d.interrupted) if d.has_data else "–",
                    _num(d.accuracy_mean),
                    _secs(d.median_response_ms),
                    _num(d.hints_per_result, 1),
                ]
                for d in s.daily
            ],
            [34 * mm, 26 * mm, 22 * mm, 26 * mm, 30 * mm, 22 * mm],
        )
    )

    # Baseline
    story.append(p("Compared with this person's usual pattern", h2))
    if s.baseline.status == "compared":
        labels = {
            "accuracy_mean": "Average score",
            "median_response_ms": "Typical response time",
            "interruption_rate": "Share stopped part-way",
            "hints_per_result": "Hints per activity",
            "mean_difficulty": "Average difficulty level",
        }
        story.append(
            p(
                f"Usual pattern = {s.baseline.results} activities between "
                f"{_day(s.baseline.from_date)} "
                f"and {_day(s.baseline.to_date)}.",
                small,
            )
        )

        def fmt(metric: str, v: float | None) -> str:
            if metric == "median_response_ms":
                return _secs(v)
            if metric == "interruption_rate":
                return _pct(v)
            return _num(v)

        story.append(
            table(
                [["Measure", "Usual", "This period"]]
                + [
                    [
                        labels.get(cmp.metric, cmp.metric),
                        fmt(cmp.metric, cmp.baseline),
                        fmt(cmp.metric, cmp.current),
                    ]
                    for cmp in s.baseline.comparisons
                ],
                [80 * mm, 45 * mm, 45 * mm],
            )
        )
    else:
        story.append(
            p("No comparison was made because there is not enough earlier activity (see above).")
        )

    # Review prompts
    story.append(p("Review prompts", h2))
    if s.review_flags:
        story.append(
            p(
                "These suggest that a repeated change may be worth discussing. "
                "They are not findings "
                "and do not indicate any condition.",
                small,
            )
        )
        for flag in s.review_flags:
            story.append(
                KeepTogether(
                    [
                        p(
                            f"{flag.title} ({flag.rule_id})",
                            ParagraphStyle("ft", parent=body, fontName=bold),
                        ),
                        p(flag.explanation),
                        p(
                            "Numbers used: "
                            + ", ".join(f"{k} = {v}" for k, v in flag.numbers.items()),
                            small,
                        ),
                    ]
                )
            )
    else:
        story.append(p("No review prompts were raised for this period."))
    if s.rules_not_evaluated:
        story.append(
            p(
                "Not checked: "
                + "; ".join(f"{r.rule_id} ({r.reason})" for r in s.rules_not_evaluated)
                + ".",
                small,
            )
        )

    # Caregiver observations
    story.append(p("Caregiver observations", h2))
    if data.observations:
        story.append(
            table(
                [["When", "Topic", "Status", "Note"]]
                + [
                    [f"{o.observed_at.astimezone(tz):%d %b %H:%M}", o.category, o.status, o.note]
                    for o in data.observations
                ],
                [28 * mm, 22 * mm, 20 * mm, 100 * mm],
            )
        )
    else:
        story.append(p("No caregiver observations were recorded in this period."))

    # Methodology
    r = data.config.review
    cfg_b, cfg_p = data.config.baseline, data.config.period
    story += [p("How this summary was made", h2)]
    story += [p("• " + line, small) for line in s.methodology]
    story.append(
        p(
            f"• Settings {data.config.config_version}: "
            f"earlier window {cfg_b.window_days} days "
            f"(at least {cfg_b.min_results} results on {cfg_b.min_days} days); "
            f"period needs {cfg_p.min_results} results on {cfg_p.min_days} days; "
            f"a change must appear on at least {r.min_share_of_days:.0%} of days with data "
            f"(score drop {r.accuracy_drop}, response time +{r.response_time_increase:.0%}, "
            f"stopped part-way +{r.interruption_rate_increase:.0%}, "
            f"hints +{r.hint_rate_increase}).",
            small,
        )
    )
    story.append(Spacer(1, 6))
    story.append(notice([s.disclaimer]))

    def footer(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont(regular, 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(20 * mm, 10 * mm, "SNEHA activity summary · not a medical assessment")
        canvas.drawRightString(190 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="SNEHA activity summary",
        author="SNEHA",
        subject=f"Activity summary {s.from_date} to {s.to_date}",
        pageCompression=1 if compress else 0,
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
