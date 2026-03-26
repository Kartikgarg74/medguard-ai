"""Report generation — HTML rendering from Jinja2 templates."""

from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.utils.logger import get_logger

logger = get_logger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"
REPORTS_DIR = Path("data/reports")


def _get_jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
    )


def render_violation_report(
    period: str,
    total_checked: int,
    total_violations: int,
    compliance_rate: float,
    violations: list[dict],
    platform_stats: dict,
    narrative: str = "",
) -> str:
    """Render a violation report as HTML."""
    env = _get_jinja_env()
    template = env.get_template("violation_report.html")

    return template.render(
        period=period,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        total_checked=total_checked,
        total_violations=total_violations,
        compliance_rate=round(compliance_rate, 1),
        violations=violations[:50],  # Top 50 violations
        platform_stats=platform_stats,
        narrative=narrative,
    )


def render_daily_summary(
    date_str: str,
    stats: dict,
    top_violations: list[dict],
    platform_breakdown: dict,
) -> str:
    """Render a daily summary report as HTML."""
    env = _get_jinja_env()
    template = env.get_template("daily_summary.html")

    return template.render(
        date=date_str,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        stats=stats,
        top_violations=top_violations[:10],
        platform_breakdown=platform_breakdown,
    )


def save_report_html(html_content: str, filename: str) -> str:
    """Save HTML report to disk. Returns file path."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    file_path = REPORTS_DIR / filename
    file_path.write_text(html_content, encoding="utf-8")
    logger.info(f"Report saved: {file_path}")
    return str(file_path)
