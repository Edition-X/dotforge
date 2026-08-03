#!/usr/bin/env python3
"""
build_plan.py — wrap an HTML body fragment in the plan-to-html template.

You author the BODY of the plan as an HTML fragment (a series of
<section class="sec" id="..."><h2>Title</h2>...</section> blocks, using the
components documented in references/components.md). This script injects that
fragment into assets/template.html, auto-builds the table of contents from the
sections, fills in the header metadata, writes a single self-contained .html
file to the output directory, and opens it in the browser.

Why a script: it keeps the design (CSS/JS) pristine and identical on every run,
generates a TOC that always matches the sections, and guarantees one
self-contained file — so each plan only needs you to write the body.

Example:
  python3 build_plan.py \\
    --title "Targeted deploy pipeline" \\
    --summary "Path-filtered deploys with a guarded deploy-all fallback." \\
    --status Proposed --effort "~1.5 days" --owner "Dan Kelly" \\
    --repo monitoring-config \\
    --body /tmp/plan-body.html
"""
import argparse
import datetime as _dt
import html as _html
import re
import sys
import webbrowser
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATE = SKILL_DIR / "assets" / "template.html"
DEFAULT_OUT_DIR = Path("/Users/dkelly/Projects/html")

# status label -> pill modifier class
STATUS_PILL = {
    "draft": "", "wip": "", "in progress": "",
    "proposed": "pill--info", "review": "pill--info", "in review": "pill--info",
    "approved": "pill--ok", "done": "pill--ok", "complete": "pill--ok", "shipped": "pill--ok",
    "blocked": "pill--danger", "at risk": "pill--warn", "on hold": "pill--warn",
}


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-{2,}", "-", text).strip("-") or "plan"


def pretty_date(d: _dt.date) -> str:
    return f"{d.day} {d:%B %Y}"


def strip_tags(s: str) -> str:
    return _html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def build_toc(body: str) -> str:
    """Find each top-level <section ... id="..."> and its first <h2>; build TOC <li>s.

    A section may set data-toc="Short label" to override the displayed text.
    """
    items = []
    for m in re.finditer(r"<section\b([^>]*)>", body, flags=re.I):
        attrs = m.group(1)
        id_m = re.search(r'\bid\s*=\s*"([^"]+)"', attrs, flags=re.I)
        if not id_m:
            continue
        sec_id = id_m.group(1)
        label_m = re.search(r'\bdata-toc\s*=\s*"([^"]+)"', attrs, flags=re.I)
        if label_m:
            label = label_m.group(1)
        else:
            h2 = re.search(r"<h2\b[^>]*>(.*?)</h2>", body[m.end():], flags=re.I | re.S)
            label = strip_tags(h2.group(1)) if h2 else sec_id
        items.append(f'      <li><a href="#{sec_id}">{_html.escape(label)}</a></li>')
    if not items:
        return '      <li><a href="#top">Overview</a></li>'
    return "\n".join(items)


def meta_item(label: str, value_html: str) -> str:
    return (f'        <span class="m"><span class="mk">{_html.escape(label)}</span>'
            f'<span class="mv">{value_html}</span></span>')


def build_meta(args, date: _dt.date) -> str:
    rows = [meta_item("Date", _html.escape(args.date or pretty_date(date)))]
    if args.status:
        cls = STATUS_PILL.get(args.status.strip().lower(), "")
        cls = f"pill {cls}".strip()
        rows.append(meta_item("Status", f'<span class="{cls}">{_html.escape(args.status)}</span>'))
    if args.effort:
        rows.append(meta_item("Effort", _html.escape(args.effort)))
    if args.owner:
        rows.append(meta_item("Owner", _html.escape(args.owner)))
    if args.repo:
        rows.append(meta_item("Repo", f"<code>{_html.escape(args.repo)}</code>"))
    return "\n".join(rows)


def unique_path(out_dir: Path, slug: str, date: _dt.date) -> Path:
    base = f"{slug}-{date.isoformat()}"
    cand = out_dir / f"{base}.html"
    n = 2
    while cand.exists():
        cand = out_dir / f"{base}-{n}.html"
        n += 1
    return cand


def main() -> int:
    p = argparse.ArgumentParser(description="Render a plan body fragment into a self-contained HTML doc.")
    p.add_argument("--title", required=True, help="Plan title (H1).")
    p.add_argument("--body", required=True, help="Path to the HTML body fragment file.")
    p.add_argument("--summary", default="", help="One- or two-sentence summary under the title.")
    p.add_argument("--kicker", default="Implementation Plan", help="Small label above the title.")
    p.add_argument("--status", default="Draft", help="Draft / Proposed / Approved / Blocked / ...")
    p.add_argument("--effort", default="", help="Effort or timeline estimate, e.g. '~2 days'.")
    p.add_argument("--owner", default="", help="Owner / author name.")
    p.add_argument("--repo", default="", help="Repo or project the plan targets.")
    p.add_argument("--date", default="", help="Override the displayed date string (default: today).")
    p.add_argument("--slug", default="", help="Override the output filename slug.")
    p.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Output directory.")
    p.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="Template path.")
    p.add_argument("--no-open", action="store_true", help="Do not open the file in a browser.")
    p.add_argument("--print-path-only", action="store_true", help="Print only the output path.")
    args = p.parse_args()

    template_path = Path(args.template)
    body_path = Path(args.body)
    out_dir = Path(args.out_dir)

    if not template_path.is_file():
        print(f"error: template not found: {template_path}", file=sys.stderr)
        return 1
    if not body_path.is_file():
        print(f"error: body fragment not found: {body_path}", file=sys.stderr)
        return 1

    today = _dt.date.today()
    template = template_path.read_text(encoding="utf-8")
    body = body_path.read_text(encoding="utf-8").strip()

    summary_html = f'<p class="summary">{_html.escape(args.summary)}</p>' if args.summary else ""
    footer = (f'Generated {pretty_date(today)} &middot; '
              f'single self-contained file &middot; toggle theme or print to PDF from the top bar.')

    out = (template
           .replace("{{TITLE}}", _html.escape(args.title))
           .replace("{{KICKER}}", _html.escape(args.kicker))
           .replace("{{SUMMARY}}", summary_html)
           .replace("{{META_ROW}}", build_meta(args, today))
           .replace("{{TOC}}", build_toc(body))
           .replace("{{BODY}}", body)
           .replace("{{FOOTER}}", footer))

    out_dir.mkdir(parents=True, exist_ok=True)
    slug = args.slug or slugify(args.title)
    dest = unique_path(out_dir, slug, today)
    dest.write_text(out, encoding="utf-8")

    if args.print_path_only:
        print(dest)
    else:
        print(f"Wrote plan: {dest}")
    if not args.no_open:
        try:
            webbrowser.open(dest.as_uri())
        except Exception as e:  # headless / no browser
            print(f"(could not open browser: {e})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
