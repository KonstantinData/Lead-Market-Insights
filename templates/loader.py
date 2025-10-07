from pathlib import Path


TEMPLATE_ROOT = Path(__file__).parent


def render_template(name: str, context: dict) -> str:
    p = TEMPLATE_ROOT / name
    txt = p.read_text(encoding="utf-8")
    out = txt
    for k, v in context.items():
        out = out.replace(f"{{{{ {k} }}}}", str(v))
    return out
