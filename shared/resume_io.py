"""Resume I/O — PDF↔Markdown conversion and unified loader.

Used by match_agent and resume_optimizer so both pick up the same resume.

Picker priority (highest first): .md  >  .txt  >  .pdf

PDF flow (no LLM, deterministic):
  pdfplumber → text + per-line font stats → heuristic Markdown.
  Cached at profile/.cache/{stem}.{md5_short}.md (keyed by PDF bytes hash) so
  re-runs are zero-cost. Cache also stores .style.json with font hierarchy
  used by Phase B (MD→PDF) to mimic the source PDF typography.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Iterable

# Heuristic thresholds for PDF→MD conversion.
_BULLET_CHARS = ("•", "▪", "●", "⁃", "∙", "·", "-", "*", "▪")
_BULLET_RE = re.compile(r"^\s*[" + "".join(re.escape(c) for c in _BULLET_CHARS) + r"]\s+")
_ALL_CAPS_HEADER_RE = re.compile(r"^[A-Z0-9][A-Z0-9 &/\-,()'.]{2,}$")


def _short_hash(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()[:10]


def _cache_dir(profile_dir: str) -> str:
    d = os.path.join(profile_dir, ".cache")
    os.makedirs(d, exist_ok=True)
    return d


def _is_bullet(line: str) -> bool:
    return bool(_BULLET_RE.match(line))


def _strip_bullet(line: str) -> str:
    return _BULLET_RE.sub("", line, count=1).strip()


def _looks_like_header(line: str, body_size: float, line_size: float) -> bool:
    """A line is a section header if it's all-caps short text or visibly larger
    than the body font."""
    s = line.strip()
    if not s or len(s) > 80:
        return False
    if line_size and body_size and line_size >= body_size * 1.15:
        # Visibly bigger than body — header by font size.
        return True
    return bool(_ALL_CAPS_HEADER_RE.match(s)) and len(s.split()) <= 8


def _extract_with_layout(pdf_path: str) -> tuple[list[dict], dict]:
    """Return (lines, style) where:
      lines = [{"text": str, "size": float}, ...]
      style = {"body_size": float, "h1_size": float, "font_family": str}
    """
    import pdfplumber  # local import — heavy dep

    lines: list[dict] = []
    sizes: list[float] = []
    fonts: list[str] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(extra_attrs=["size", "fontname"], use_text_flow=True)
            if not words:
                continue
            # Group words into lines by y-position (top within ~2pt).
            words_sorted = sorted(words, key=lambda w: (round(float(w["top"]), 0), float(w["x0"])))
            current_top = None
            buf: list[dict] = []
            def flush():
                if not buf:
                    return
                text = " ".join(w["text"] for w in buf).strip()
                if not text:
                    return
                # Use the median size of the line.
                ss = sorted(float(w.get("size", 0) or 0) for w in buf)
                size = ss[len(ss) // 2] if ss else 0.0
                lines.append({"text": text, "size": size})
                sizes.append(size)
                for w in buf:
                    fn = w.get("fontname")
                    if fn:
                        fonts.append(fn)
            for w in words_sorted:
                top = round(float(w["top"]), 0)
                if current_top is None or abs(top - current_top) <= 2:
                    buf.append(w)
                    current_top = top if current_top is None else current_top
                else:
                    flush()
                    buf = [w]
                    current_top = top
            flush()
            # Page break — blank line marker.
            lines.append({"text": "", "size": 0.0})

    # Style: body = mode of common sizes; h1 = max distinct size.
    body_size = 0.0
    h1_size = 0.0
    if sizes:
        nonzero = [s for s in sizes if s > 0]
        if nonzero:
            # Mode-ish: most common rounded size.
            buckets: dict[int, int] = {}
            for s in nonzero:
                k = int(round(s))
                buckets[k] = buckets.get(k, 0) + 1
            body_size = float(max(buckets, key=buckets.get))
            h1_size = float(max(nonzero))
    family = _normalize_font_family(fonts)

    style = {"body_size": body_size, "h1_size": h1_size, "font_family": family}
    return lines, style


def _normalize_font_family(fonts: list[str]) -> str:
    """Map embedded PostScript font names to a CSS-friendly family.

    ATS-safe: always falls back to a generic sans-serif/serif stack.
    """
    if not fonts:
        return "Helvetica, Arial, sans-serif"
    # Take the most common family stem.
    stems: dict[str, int] = {}
    for f in fonts:
        # "ABCDEF+Helvetica-Bold" -> "Helvetica"
        stem = f.split("+", 1)[-1].split("-", 1)[0].split(",", 1)[0]
        stems[stem] = stems.get(stem, 0) + 1
    top = max(stems, key=stems.get).lower()
    if "times" in top or "serif" in top:
        return "'Times New Roman', Times, serif"
    if "arial" in top:
        return "Arial, Helvetica, sans-serif"
    if "calibri" in top:
        return "Calibri, 'Segoe UI', Arial, sans-serif"
    if "georgia" in top:
        return "Georgia, 'Times New Roman', serif"
    # Default ATS-safe stack.
    return "Helvetica, Arial, sans-serif"


def _lines_to_markdown(lines: list[dict], style: dict) -> str:
    """Convert layout-aware lines to markdown using header/bullet heuristics."""
    body_size = style.get("body_size", 0.0)
    out: list[str] = []
    prev_blank = True
    for ln in lines:
        text = ln["text"]
        size = ln.get("size", 0.0)
        if not text:
            if not prev_blank:
                out.append("")
                prev_blank = True
            continue
        if _is_bullet(text):
            out.append(f"- {_strip_bullet(text)}")
            prev_blank = False
            continue
        if _looks_like_header(text, body_size, size):
            if not prev_blank:
                out.append("")
            out.append(f"## {text.strip()}")
            out.append("")
            prev_blank = True
            continue
        out.append(text.strip())
        prev_blank = False
    # Collapse trailing blanks.
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


def pdf_to_markdown(pdf_path: str) -> tuple[str, dict]:
    """Convert a PDF resume to Markdown. Returns (markdown_text, style_dict)."""
    lines, style = _extract_with_layout(pdf_path)
    md = _lines_to_markdown(lines, style)
    return md, style


def _convert_and_cache(pdf_path: str, profile_dir: str) -> tuple[str, str, dict]:
    """Convert PDF→MD and cache. Returns (md_text, cache_md_path, style)."""
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    short = _short_hash(pdf_bytes)
    stem = os.path.splitext(os.path.basename(pdf_path))[0]
    cdir = _cache_dir(profile_dir)
    md_cache = os.path.join(cdir, f"{stem}.{short}.md")
    style_cache = os.path.join(cdir, f"{stem}.{short}.style.json")

    if os.path.exists(md_cache) and os.path.exists(style_cache):
        with open(md_cache, encoding="utf-8") as f:
            md = f.read()
        with open(style_cache, encoding="utf-8") as f:
            style = json.load(f)
        logging.info(f"Loaded cached PDF→MD: {md_cache}")
        return md, md_cache, style

    md, style = pdf_to_markdown(pdf_path)
    with open(md_cache, "w", encoding="utf-8") as f:
        f.write(md)
    with open(style_cache, "w", encoding="utf-8") as f:
        json.dump(style, f, indent=2)
    logging.info(f"Converted PDF→MD: {pdf_path} → {md_cache}")
    return md, md_cache, style


def _pick_resume_file(folder: str) -> str | None:
    """Pick the best resume file from folder. Priority: .md > .txt > .pdf."""
    if not os.path.exists(folder):
        return None
    candidates: dict[str, list[str]] = {".md": [], ".txt": [], ".pdf": []}
    for fname in os.listdir(folder):
        if fname.startswith(".") or fname.startswith("_"):
            continue
        ext = os.path.splitext(fname)[1].lower()
        if ext in candidates:
            candidates[ext].append(fname)
    for ext in (".md", ".txt", ".pdf"):
        if candidates[ext]:
            return os.path.join(folder, sorted(candidates[ext])[0])
    return None


def load_resume(folder: str) -> tuple[str, str]:
    """Load resume from folder. Returns (text, resume_id).

    Picker priority: .md > .txt > .pdf. PDFs are converted to Markdown via
    pdfplumber and cached at profile/.cache/{stem}.{md5_short}.md.

    resume_id is the source file's stem (e.g. Resume_0428.pdf → Resume_0428)
    so Excel keys remain stable across input formats.
    """
    if not os.path.exists(folder):
        logging.error(f"Profile folder not found: {folder}")
        return "", ""
    path = _pick_resume_file(folder)
    if not path:
        logging.error(f"No .md/.txt/.pdf resume in {folder}")
        return "", ""

    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        text, _, _ = _convert_and_cache(path, folder)
    else:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()

    resume_id = os.path.splitext(os.path.basename(path))[0]
    logging.info(f"Loaded resume: {os.path.basename(path)}  ({len(text)} chars)")
    return text, resume_id


# ── MD → PDF (Phase B) ────────────────────────────────────────────────────────
_DEFAULT_CSS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "resume.css"
)


def _md_to_html(md_text: str) -> str:
    """Minimal markdown → HTML for resume content.

    Supports: # / ## / ### headings, '- ' bullets, **bold**, *italic*, blank-line
    paragraphs, and `[text](url)` links. Deliberately small — resumes don't need
    tables/code/images, and avoiding a heavy markdown lib keeps the dep surface
    small. ATS-safe by construction (only structural HTML, no graphics).
    """
    import html as _html

    # Strip pandoc-style attribute spans before parsing.
    #   "[text]{.underline}"            → "text"
    #   "[[text]{.underline}](url)"     → "[text](url)"   (link is preserved)
    md_text = re.sub(r"\[\[([^\]]+)\]\{\.[a-zA-Z0-9_-]+\}\]\(([^)]+)\)", r"[\1](\2)", md_text)
    md_text = re.sub(r"\[([^\]]+)\]\{\.[a-zA-Z0-9_-]+\}", r"\1", md_text)

    lines = md_text.splitlines()
    out: list[str] = []
    in_list = False

    def close_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    def inline(text: str) -> str:
        # Escape first, then re-introduce supported markup.
        s = _html.escape(text)
        # Links: [label](url)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
        # Bold then italic (greedy-safe non-greedy).
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
        return s

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            close_list()
            continue
        if line.startswith("### "):
            close_list()
            out.append(f"<h3>{inline(line[4:].strip())}</h3>")
            continue
        if line.startswith("## "):
            close_list()
            out.append(f"<h2>{inline(line[3:].strip())}</h2>")
            continue
        if line.startswith("# "):
            close_list()
            out.append(f"<h1>{inline(line[2:].strip())}</h1>")
            continue
        if re.match(r"^\s*[-*]\s+", line):
            if not in_list:
                out.append("<ul>")
                in_list = True
            item = re.sub(r"^\s*[-*]\s+", "", line)
            out.append(f"<li>{inline(item)}</li>")
            continue
        # Plain paragraph.
        close_list()
        out.append(f"<p>{inline(line)}</p>")
    close_list()
    return "\n".join(out)


def _build_html_doc(body_html: str, style: dict | None) -> str:
    """Wrap body HTML in a full HTML doc; inject CSS variable overrides from style."""
    overrides: list[str] = []
    if style:
        family = style.get("font_family")
        if family:
            overrides.append(f"--resume-font-family: {family};")
        body_size = style.get("body_size")
        if body_size and body_size > 0:
            # Clamp to [9pt, 12pt] for ATS readability.
            pt = max(9.0, min(12.0, float(body_size)))
            overrides.append(f"--resume-body-size: {pt:.1f}pt;")
    var_block = ""
    if overrides:
        var_block = "<style>:root{" + " ".join(overrides) + "}</style>"
    return (
        "<!doctype html>\n<html><head><meta charset='utf-8'>"
        f"{var_block}"
        "</head><body>"
        f"{body_html}"
        "</body></html>"
    )


def markdown_to_pdf(
    md_text: str,
    out_path: str,
    *,
    style: dict | None = None,
    css_path: str | None = None,
) -> str:
    """Render Markdown → PDF using WeasyPrint with the ATS-safe stylesheet.

    Args:
        md_text: Markdown source (resume body).
        out_path: Destination .pdf path.
        style: Optional dict from pdf_to_markdown / get_style_for_resume —
               keys: font_family, body_size. Used to mimic input PDF typography.
        css_path: Override default templates/resume.css.

    Returns out_path.
    """
    from weasyprint import CSS, HTML  # local import — heavy dep

    css_file = css_path or _DEFAULT_CSS_PATH
    body_html = _md_to_html(md_text)
    doc = _build_html_doc(body_html, style)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    HTML(string=doc).write_pdf(out_path, stylesheets=[CSS(filename=css_file)])
    return out_path


def get_style_for_resume(folder: str) -> dict | None:
    """Return cached style dict for the picked PDF resume, or None.

    Used by Phase B (MD→PDF) to mimic the source typography. Returns None if
    the picked resume isn't a PDF (caller should use defaults).
    """
    path = _pick_resume_file(folder)
    if not path or not path.lower().endswith(".pdf"):
        return None
    with open(path, "rb") as f:
        short = _short_hash(f.read())
    stem = os.path.splitext(os.path.basename(path))[0]
    style_cache = os.path.join(_cache_dir(folder), f"{stem}.{short}.style.json")
    if not os.path.exists(style_cache):
        return None
    with open(style_cache, encoding="utf-8") as f:
        return json.load(f)
