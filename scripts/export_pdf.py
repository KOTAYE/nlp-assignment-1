"""Export docs/report.md (with the architecture diagram) to docs/report.pdf.

Markdown -> HTML (Mermaid diagrams rendered by mermaid.js) -> PDF via headless Chrome/Edge.
Usage: python scripts/export_pdf.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "report.md"
HTML = ROOT / "logs" / "report.html"
PDF = ROOT / "docs" / "report.pdf"
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "google-chrome",
    "chromium",
    "msedge",
]

CSS = """
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10.5pt; line-height: 1.45; color: #1a1a1a; margin: 0 8mm; }
h1 { font-size: 20pt; border-bottom: 2px solid #6b3fd4; padding-bottom: 4px; }
h2 { font-size: 14pt; margin-top: 18px; border-bottom: 1px solid #ddd; padding-bottom: 2px; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin-top: 12px; page-break-after: avoid; }
table { border-collapse: collapse; width: 100%; margin: 6px 0 10px; font-size: 9pt; page-break-inside: avoid; }
th, td { border: 1px solid #ccc; padding: 3px 5px; vertical-align: top; text-align: left; }
th { background: #f1ecfb; }
code { background: #f4f4f4; padding: 0 3px; border-radius: 3px; font-size: 9pt; }
pre { background: #f6f6f6; padding: 6px; font-size: 8.5pt; white-space: pre-wrap; }
blockquote { border-left: 3px solid #6b3fd4; margin: 6px 0; padding: 2px 10px; color: #444; }
.mermaid { text-align: center; margin: 8px 0; page-break-inside: avoid; }
"""


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    # protect mermaid blocks from the markdown converter
    blocks: list[str] = []

    def keep(m: re.Match) -> str:
        blocks.append(m.group(1))
        return f"MERMAIDBLOCK{len(blocks) - 1}"

    text = re.sub(r"```mermaid\n(.*?)```", keep, text, flags=re.S)
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    for i, b in enumerate(blocks):
        body = body.replace(f"<p>MERMAIDBLOCK{i}</p>", f'<pre class="mermaid">{b}</pre>')
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>HR Assistant report</title>
<style>{CSS}</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
<script>mermaid.initialize({{startOnLoad: true, theme: 'default', flowchart: {{useMaxWidth: true}}}});</script>
</head><body>{body}</body></html>"""
    HTML.parent.mkdir(parents=True, exist_ok=True)
    HTML.write_text(html, encoding="utf-8")
    browser = next((b for b in BROWSERS if Path(b).exists() or shutil.which(b)), None)
    if not browser:
        sys.exit(f"No Chrome/Edge found. Open {HTML} in a browser and print to PDF.")
    subprocess.run(
        [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            "--virtual-time-budget=15000",
            f"--print-to-pdf={PDF}",
            HTML.as_uri(),
        ],
        check=True,
        capture_output=True,
    )
    print(f"written {PDF.relative_to(ROOT)} ({PDF.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
