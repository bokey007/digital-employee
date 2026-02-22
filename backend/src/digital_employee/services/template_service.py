"""Template service — Jinja2 rendering for newsletter HTML."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = structlog.get_logger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "templates"


class TemplateService:
    """Renders the newsletter HTML using Jinja2 templates."""

    def __init__(self, templates_dir: Path | None = None) -> None:
        path = templates_dir or TEMPLATES_DIR
        self._env = Environment(
            loader=FileSystemLoader(str(path)),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_newsletter(
        self,
        title: str,
        date: datetime,
        content_html: str,
        edition_number: int | None = None,
        anuj_instructions: bool = False,
        reviewer_name: str = "",
    ) -> str:
        """Render the full newsletter HTML with header and footer.

        Args:
            title: Newsletter title / edition name.
            date: Publication date.
            content_html: The inner content (already consolidated by LLM).
            edition_number: Optional edition number for display.
            anuj_instructions: Render the delivery leader review block at top.
            reviewer_name: Name of the reviewer for the instruction block.

        Returns:
            Complete HTML string ready for email sending.
        """
        template = self._env.get_template("newsletter.html")
        rendered = template.render(
            title=title,
            date=date.strftime("%B %Y"),
            date_full=date.strftime("%d %B %Y"),
            content=content_html,
            edition_number=edition_number,
            year=date.year,
            anuj_instructions=anuj_instructions,
            reviewer_name=reviewer_name,
        )

        try:
            from premailer import transform
            # Convert all <style> blocks in the HTML into inline style="..." attributes
            # This is critical because email clients like Gmail strip <style> blocks.
            rendered = transform(rendered)
        except ImportError:
            logger.warning("premailer not installed, skipping CSS inlining")

        logger.info("newsletter_rendered", title=title)
        return rendered
