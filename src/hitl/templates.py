"""
Jinja2-based rendering for HITL emails.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
from jinja2 import Environment, FileSystemLoader, select_autoescape
from .logging_setup import get_logger


log = get_logger("hitl.templates", "templates.log")


TPL_DIR = Path("./templates")
TPL_DIR.mkdir(parents=True, exist_ok=True)


env = Environment(
loader=FileSystemLoader(str(TPL_DIR)),
autoescape=select_autoescape(enabled_extensions=("j2",)),
)


# Explanation: render template with context; logs to file


def render(template_name: str, context: Dict[str, Any]) -> str:
tpl = env.get_template(template_name)
body = tpl.render(**context)
log.info("template_rendered", extra={"template": template_name})
return body