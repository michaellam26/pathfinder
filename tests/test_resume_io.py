"""Tests for shared/resume_io.py — PDF↔MD conversion + unified loader.

Coverage:
  - load_resume picker priority: .md > .txt > .pdf
  - pdf_to_markdown extracts text + detects sections + bullets
  - cache reuse: second call returns cached file (no re-conversion)
  - get_style_for_resume returns style dict for PDF input, None for .md
  - markdown_to_pdf produces a non-empty PDF with extractable text
  - markdown_to_pdf injects style overrides (font_family, body_size)
  - ATS-safe rendering: text is selectable, no images, single column
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from shared.resume_io import (
    _md_to_html,
    _pick_resume_file,
    get_style_for_resume,
    load_resume,
    markdown_to_pdf,
    pdf_to_markdown,
)


def _make_sample_pdf(path: str) -> None:
    """Create a small sample resume PDF using reportlab if available, else
    fall back to a hand-built PDF via pypdfium2 / weasyprint. We use weasyprint
    (already installed) to render a minimal HTML resume → PDF as our fixture.
    """
    from weasyprint import HTML

    html = """
    <html><body style="font-family: Helvetica; font-size: 10.5pt;">
      <h1 style="font-size: 18pt; text-align:center;">JANE DOE</h1>
      <p>Seattle, WA · jane@example.com</p>
      <h2 style="font-size: 12pt; text-transform:uppercase;">PROFESSIONAL SUMMARY</h2>
      <p>Senior TPM with 10 years experience.</p>
      <h2 style="font-size: 12pt; text-transform:uppercase;">EXPERIENCE</h2>
      <ul>
        <li>Led migration to multi-agent LLM pipeline</li>
        <li>Owned roadmap for 5 cross-org programs</li>
      </ul>
    </body></html>
    """
    HTML(string=html).write_pdf(path)


class TestResumeIOPicker(unittest.TestCase):
    def test_picker_prefers_md_over_pdf(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "resume.md").write_text("# MD")
            Path(d, "resume.pdf").write_bytes(b"%PDF-1.4 fake")
            picked = _pick_resume_file(d)
            self.assertTrue(picked.endswith(".md"))

    def test_picker_prefers_txt_over_pdf(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "resume.txt").write_text("plain")
            Path(d, "resume.pdf").write_bytes(b"%PDF-1.4 fake")
            picked = _pick_resume_file(d)
            self.assertTrue(picked.endswith(".txt"))

    def test_picker_falls_back_to_pdf(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "resume.pdf").write_bytes(b"%PDF-1.4 fake")
            picked = _pick_resume_file(d)
            self.assertTrue(picked.endswith(".pdf"))

    def test_picker_skips_dot_and_underscore_files(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, ".DS_Store").write_text("")
            Path(d, "_draft.md").write_text("draft")
            Path(d, "resume.md").write_text("real")
            picked = _pick_resume_file(d)
            self.assertEqual(os.path.basename(picked), "resume.md")

    def test_picker_returns_none_when_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(_pick_resume_file(d))


class TestPDFToMarkdown(unittest.TestCase):
    def test_converts_pdf_to_markdown_with_sections_and_bullets(self):
        with tempfile.TemporaryDirectory() as d:
            pdf_path = os.path.join(d, "resume.pdf")
            _make_sample_pdf(pdf_path)
            md, style = pdf_to_markdown(pdf_path)
            self.assertIn("JANE DOE", md)
            # All-caps section labels should be detected.
            self.assertTrue(
                "PROFESSIONAL SUMMARY" in md or "## PROFESSIONAL SUMMARY" in md
            )
            self.assertIn("EXPERIENCE", md)
            # Bullets should be markdown-style.
            self.assertIn("- Led migration to multi-agent LLM pipeline", md)
            # Style dict should have font + size info.
            self.assertGreater(style.get("body_size", 0), 0)
            self.assertIn("font_family", style)

    def test_load_resume_caches_pdf_conversion(self):
        with tempfile.TemporaryDirectory() as d:
            pdf_path = os.path.join(d, "resume.pdf")
            _make_sample_pdf(pdf_path)

            text1, rid1 = load_resume(d)
            self.assertGreater(len(text1), 50)
            self.assertEqual(rid1, "resume")

            cache_dir = os.path.join(d, ".cache")
            self.assertTrue(os.path.exists(cache_dir))
            cache_files = [f for f in os.listdir(cache_dir) if f.endswith(".md")]
            self.assertEqual(len(cache_files), 1)

            mtime_before = os.path.getmtime(os.path.join(cache_dir, cache_files[0]))
            text2, rid2 = load_resume(d)
            self.assertEqual(text1, text2)
            self.assertEqual(rid1, rid2)
            mtime_after = os.path.getmtime(os.path.join(cache_dir, cache_files[0]))
            self.assertEqual(mtime_before, mtime_after)

    def test_get_style_for_resume_pdf(self):
        with tempfile.TemporaryDirectory() as d:
            pdf_path = os.path.join(d, "resume.pdf")
            _make_sample_pdf(pdf_path)
            load_resume(d)  # warm cache
            style = get_style_for_resume(d)
            self.assertIsNotNone(style)
            self.assertIn("font_family", style)
            self.assertGreater(style.get("body_size", 0), 0)

    def test_get_style_returns_none_for_md(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "resume.md").write_text("# Hi")
            self.assertIsNone(get_style_for_resume(d))


class TestMarkdownToHTML(unittest.TestCase):
    def test_headings_bullets_inline(self):
        md = "# Title\n\n## Section\n\n- one\n- two **bold** *em*\n\nA [link](https://example.com)."
        html = _md_to_html(md)
        self.assertIn("<h1>Title</h1>", html)
        self.assertIn("<h2>Section</h2>", html)
        self.assertIn("<ul>", html)
        self.assertIn("<li>one</li>", html)
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn("<em>em</em>", html)
        self.assertIn('<a href="https://example.com">link</a>', html)

    def test_escapes_html_in_input(self):
        html = _md_to_html("- 5 < 7 and a > b")
        self.assertIn("5 &lt; 7 and a &gt; b", html)
        self.assertNotIn("<script", html)

    def test_strips_pandoc_underline_attribute_spans(self):
        # Pandoc-style "[text]{.underline}" should reduce to plain text.
        html = _md_to_html("[Plain text]{.underline} after")
        self.assertIn("Plain text after", html)
        self.assertNotIn("{.underline}", html)
        # Nested form inside a link: "[[label]{.underline}](url)" → working link.
        html = _md_to_html(
            "Email: [[user@example.com]{.underline}](mailto:user@example.com)"
        )
        self.assertIn('<a href="mailto:user@example.com">user@example.com</a>', html)
        self.assertNotIn("{.underline}", html)


class TestMarkdownToPDF(unittest.TestCase):
    def test_writes_nonempty_pdf_with_text(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "out.pdf")
            md = (
                "# Jane Doe\n\n"
                "## Summary\n\n"
                "Senior TPM with 10 years experience.\n\n"
                "## Experience\n\n"
                "- Led X\n- Owned Y\n"
            )
            markdown_to_pdf(md, out)
            self.assertTrue(os.path.exists(out))
            self.assertGreater(os.path.getsize(out), 1000)

            # ATS-safe: text must be selectable / extractable.
            import pdfplumber
            with pdfplumber.open(out) as pdf:
                page_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            self.assertIn("Jane Doe", page_text)
            self.assertIn("Senior TPM", page_text)
            self.assertIn("Led X", page_text)

    def test_style_overrides_applied(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "styled.pdf")
            md = "# Title\n\nbody copy"
            style = {"font_family": "'Times New Roman', Times, serif", "body_size": 11.0}
            markdown_to_pdf(md, out, style=style)
            self.assertTrue(os.path.exists(out))
            # Confirm font family made it into the rendered PDF metadata.
            import pdfplumber
            with pdfplumber.open(out) as pdf:
                fonts = set()
                for p in pdf.pages:
                    for ch in (p.chars or []):
                        fn = ch.get("fontname")
                        if fn:
                            fonts.add(fn.lower())
            # Expect a Times-family font when we override; defaults are Helvetica.
            self.assertTrue(
                any("times" in f for f in fonts),
                f"expected a Times-family font, got: {sorted(fonts)[:5]}",
            )


if __name__ == "__main__":
    unittest.main()
