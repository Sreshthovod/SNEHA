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
    fatigue_level: str | None = None


@dataclass(frozen=True)
class ReviewItemLine:
    rule_id: str
    title: str
    explanation: str
    numbers: dict
    status: str  # awaiting_review | confirmed | dismissed
    decided_at: datetime | None = None
    decision_reason: str | None = None
    results_considered: int | None = None
    context_notes: tuple[tuple[datetime, str], ...] = ()


@dataclass(frozen=True)
class TirednessCounts:
    """Tiredness reports in the period, by who reported them. Each report counted once."""

    patient_button: int = 0  # "I'm tired" on the phone
    caregiver_phone_mild: int = 0
    caregiver_phone_severe: int = 0
    dashboard_mild: int = 0
    dashboard_severe: int = 0
    dashboard_no_level: int = 0

    @property
    def total(self) -> int:
        return (
            self.patient_button
            + self.caregiver_phone_mild
            + self.caregiver_phone_severe
            + self.dashboard_mild
            + self.dashboard_severe
            + self.dashboard_no_level
        )


@dataclass(frozen=True)
class ReportInput:
    report_id: str
    patient_name: str
    summary: AnalyticsSummary
    observations: list[ObservationLine]
    config: AnalyticsConfig
    generated_at: datetime
    review_items: list[ReviewItemLine] | None = None
    tiredness: TirednessCounts | None = None


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
            "Both dates are included: the period runs from the start of the first day to the "
            f"end of the last day in {s.timezone}. Activities are counted on the day they "
            "finished; sessions on the day they started.",
            small,
        ),
        p(
            f"Generated {data.generated_at.astimezone(tz):%d %b %Y %H:%M} ({s.timezone}) · "
            f"Report {data.report_id} · Method {s.method_version}, settings {s.config_version}",
            small,
        ),
        Spacer(1, 6),
        notice(["Important: " + s.disclaimer]),
    ]

    part = ParagraphStyle("part", parent=h1, fontSize=14.5, leading=18, spaceBefore=12)
    story += [
        Spacer(1, 4),
        p(
            "This report has three parts. Part 1 is what was recorded. Part 2 is what the "
            "automatic rules point out (an interpretation, not a finding). Part 3 is what a "
            "caregiver has confirmed as worth discussing with a clinician.",
            small,
        ),
        p("Part 1. What was recorded", part),
        p(
            "Counts and measures straight from stored activity records and caregiver notes. "
            "Nothing is estimated and missing days are not filled in.",
            small,
        ),
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
            "No comparison with this person's usual pattern"
            + (f": {s.baseline.reason}" if s.baseline.reason else "")
            + f" (needs {s.baseline.required_results} results on {s.baseline.required_days} "
            f"days of the same activities in the "
            f"{(s.baseline.to_date - s.baseline.from_date).days + 1} days before; found "
            f"{s.baseline.results} on {s.baseline.days})."
        )
    if s.sync and s.sync.may_be_incomplete:
        last = (
            f"{s.sync.last_phone_sync_at.astimezone(tz):%d %b %Y %H:%M}"
            if s.sync.last_phone_sync_at
            else "never"
        )
        warnings.append(
            f"This report may be incomplete: {s.sync.reason} (last shared: {last}). "
            "Activities recorded on the phone without internet appear once it syncs."
        )
    t0 = s.totals
    if t0.sessions_in_progress or t0.sessions_interrupted:
        warnings.append(
            f"Sessions not finished normally: {t0.sessions_interrupted} interrupted (the app was "
            f"closed during an activity), {t0.sessions_in_progress} not ended yet. They are "
            "counted separately, never as completed or failed."
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
                f"and {_day(s.baseline.to_date)}. Only activities played in both periods are "
                "compared (like with like): "
                + ", ".join(s.baseline.activities_compared)
                + "."
                + (
                    " Not compared (played in this period only): "
                    + ", ".join(s.baseline.activities_not_compared)
                    + "."
                    if s.baseline.activities_not_compared
                    else ""
                ),
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
        if s.baseline.per_activity:
            story.append(
                table(
                    [["Activity", "Activities (usual / now)", "Score", "Response", "Hints"]]
                    + [
                        [
                            a.title,
                            f"{a.baseline_results} / {a.period_results}",
                            f"{_num(a.baseline_accuracy)} → {_num(a.period_accuracy)}",
                            f"{_secs(a.baseline_median_response_ms)} → "
                            f"{_secs(a.period_median_response_ms)}",
                            f"{_num(a.baseline_hints_per_result, 1)} → "
                            f"{_num(a.period_hints_per_result, 1)}",
                        ]
                        for a in s.baseline.per_activity
                    ],
                    [50 * mm, 32 * mm, 28 * mm, 34 * mm, 26 * mm],
                )
            )
    else:
        story.append(
            p("No comparison was made" + (f": {s.baseline.reason}." if s.baseline.reason else "."))
        )

    # Support given during activities (activity events)
    story.append(p("Support given during activities", h2))
    sup = s.support
    if sup is None or not sup.sessions_with_events:
        story.append(
            p(
                "No step-by-step record for the sessions in this period (recorded by an older "
                "app version, or not shared yet). Nothing is assumed."
            )
        )
    else:
        adj = sup.adjustments or {}
        story.append(
            table(
                [
                    ["What happened", "Count"],
                    ["Hints the person asked for", str(sup.hints_asked_for or 0)],
                    [
                        "Hints the app gave after wrong answers",
                        str(sup.hints_given_automatically or 0),
                    ],
                    ["Questions read aloud again on request", str(sup.read_aloud_presses or 0)],
                    ["Pauses by the person", str(sup.pauses_by_person or 0)],
                    ["Pauses because the phone left the screen", str(sup.pauses_screen_left or 0)],
                    [
                        "Rests offered and taken / declined",
                        f"{sup.rests_taken or 0} / {sup.rests_declined or 0}",
                    ],
                    ["Activities shortened by the app", str(adj.get("shorten", 0))],
                    ["Stop requests", str(sup.stop_requests or 0)],
                ],
                [120 * mm, 50 * mm],
            )
        )
        story.append(
            p(
                f"From the step-by-step record of {sup.sessions_with_events} of "
                f"{sup.sessions_started} sessions. Support is a sign the app adapted, not a "
                "measure of the person.",
                small,
            )
        )

    # Tiredness reports
    story.append(p("Tiredness reports", h2))
    tired = data.tiredness or TirednessCounts()
    if tired.total == 0:
        story.append(p("No tiredness was reported in this period."))
    else:
        story.append(
            table(
                [
                    ["Reported by", "A little tired", "Very tired", "Level not given"],
                    ['The person ("I\'m tired" button)', "–", "–", str(tired.patient_button)],
                    [
                        "A caregiver, on the person's phone",
                        str(tired.caregiver_phone_mild),
                        str(tired.caregiver_phone_severe),
                        "–",
                    ],
                    [
                        "A caregiver, on the dashboard",
                        str(tired.dashboard_mild),
                        str(tired.dashboard_severe),
                        str(tired.dashboard_no_level),
                    ],
                ],
                [70 * mm, 33 * mm, 33 * mm, 34 * mm],
            )
        )
        story.append(
            p(
                "Each report is counted once. A tiredness report makes the app easier and "
                "shorter, or stops it; it is never counted as a mistake.",
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
                    [
                        f"{o.observed_at.astimezone(tz):%d %b %H:%M}",
                        o.category
                        + (
                            {"mild": " (a little tired)", "severe": " (very tired)"}.get(
                                o.fatigue_level or "", ""
                            )
                        ),
                        o.status,
                        o.note,
                    ]
                    for o in data.observations
                ],
                [26 * mm, 40 * mm, 18 * mm, 86 * mm],
            )
        )
        story.append(p("Notes are printed exactly as the caregiver wrote them.", small))
    else:
        story.append(p("No caregiver observations were recorded in this period."))

    # Part 2: automatic rules (interpretation)
    items = data.review_items or []
    by_rule = {i.rule_id: i for i in items}
    story += [
        p("Part 2. What the automatic rules point out", part),
        p(
            "Review prompts compare this period with the person's own earlier activity using "
            "fixed, published rules (below). They are interpretations of game behaviour, not "
            "findings, and do not indicate any condition. A prompt only becomes something to "
            "discuss with a clinician when a caregiver confirms it (Part 3).",
            small,
        ),
        p("Review prompts", h2),
    ]
    if s.review_flags:
        for flag in s.review_flags:
            item = by_rule.get(flag.rule_id)
            state = {
                None: "Not yet reviewed by a caregiver.",
                "awaiting_review": "Awaiting caregiver review. Not a concern unless confirmed.",
                "confirmed": "Confirmed by a caregiver (see Part 3).",
                "dismissed": "Dismissed by a caregiver (see Part 3).",
            }[item.status if item else None]
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
                        p("Status: " + state, small),
                    ]
                )
            )
    else:
        story.append(p("No review prompts were raised for this period."))
    if s.rules_not_evaluated:
        story.append(
            p(
                "Not checked, because there was not enough data: "
                + "; ".join(f"{r.rule_id} ({r.reason})" for r in s.rules_not_evaluated)
                + ". Too little data is never treated as a change.",
                small,
            )
        )

    # Part 3: caregiver decisions
    confirmed = [i for i in items if i.status == "confirmed"]
    dismissed = [i for i in items if i.status == "dismissed"]
    story += [
        p("Part 3. What a caregiver confirmed", part),
        p(
            "A caregiver who knows the person read each prompt and its numbers, and decided "
            "whether it is worth discussing with a clinician. Their reason is printed as "
            "written. This is still not a diagnosis.",
            small,
        ),
        p("Confirmed as worth discussing with a clinician", h2),
    ]

    def decided(i: ReviewItemLine) -> list:
        when = f"{i.decided_at.astimezone(tz):%d %b %Y}" if i.decided_at else "–"
        return [
            p(f"{i.title} ({i.rule_id})", ParagraphStyle("ct", parent=body, fontName=bold)),
            p(i.explanation),
            p(f"Caregiver's reason ({when}): {i.decision_reason or '–'}", small),
            *(
                [p(f"Based on {i.results_considered} recorded activities.", small)]
                if i.results_considered is not None
                else []
            ),
            *[
                p(f"Caregiver context ({at.astimezone(tz):%d %b %Y}): {note}", small)
                for at, note in i.context_notes
            ],
        ]

    if confirmed:
        for i in confirmed:
            story.append(KeepTogether(decided(i)))
    else:
        story.append(p("Nothing has been confirmed by a caregiver for this period."))
    if dismissed:
        story.append(p("Dismissed by a caregiver", h2))
        for i in dismissed:
            story.append(KeepTogether(decided(i)))

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
