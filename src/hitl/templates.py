"""Template rendering helpers tailored for the HITL workflow."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from .logging_setup import get_logger


log = get_logger("hitl.templates", "templates.log")

TPL_DIR = Path("./templates")
TPL_DIR.mkdir(parents=True, exist_ok=True)

_PLACEHOLDER = re.compile(r"{{\s*([^{}\s]+)\s*}}")


def _resolve(context: Mapping[str, Any], path: str) -> Any:
    value: Any = context
    for part in path.split("."):
        if isinstance(value, Mapping):
            value = value.get(part)
        else:
            value = getattr(value, part, None)
        if value is None:
            break
    return value if value is not None else ""


def render(template_name: str, context: Mapping[str, Any]) -> str:
    """Render *template_name* with *context* supporting dotted lookups."""

    template_path = TPL_DIR / template_name
    body = template_path.read_text(encoding="utf-8")

    def replacer(match: re.Match[str]) -> str:
        placeholder = match.group(1)
        return str(_resolve(context, placeholder))

    rendered = _PLACEHOLDER.sub(replacer, body)
    log.info("template_rendered", extra={"template": template_name})
    return rendered