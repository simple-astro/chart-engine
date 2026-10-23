"""The Life Book as a PDF to download (A5, cream pages, the app's own fonts), from the same chapters the app shows.

Cover, contents, then each chapter on a new page; the block types match the app's reader (p, list, rows, cards,
qa). Fonts are fixed-weight cuts of the bundled Inter and Cormorant Garamond (PDFs cannot use variable fonts).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

FONTS = Path(__file__).resolve().parent / "fonts"
LOGO = Path(__file__).resolve().parent / "static" / "sun-card.png"
CREAM, INK, MUT, ACC, LINE, SOFT = (251, 247, 239), (31, 26, 20), (107, 90, 67), (138, 94, 20), (228, 214, 187), (243, 231, 207)
TAG = {"Strong": (31, 90, 55), "Mixed": (122, 79, 0), "Needs care": (142, 58, 12)}
W, H, M = 148, 210, 16  # A5 in mm, margin


def _pdf():
    from fpdf import FPDF

    class Book(FPDF):
        def header(self):
            self.set_fill_color(*CREAM)
            self.rect(0, 0, W, H, "F")

        def footer(self):
            if self.page_no() <= 1:
                return
            self.set_y(-11)
            self.set_font("inter", "", 7.5)
            self.set_text_color(*MUT)
            self.cell(0, 4, f"{self.page_no()}", align="C")
            self.set_x(M)
            self.cell(0, 4, "simplejyotish.com", align="R")

    pdf = Book(format=(W, H), unit="mm")
    pdf.set_margins(M, M, M)
    pdf.set_auto_page_break(True, margin=16)
    pdf.add_font("inter", "", str(FONTS / "Inter-Regular.ttf"))
    pdf.add_font("inter", "B", str(FONTS / "Inter-SemiBold.ttf"))
    pdf.add_font("serif", "B", str(FONTS / "Cormorant-Bold.ttf"))
    return pdf


def _text(pdf, txt: str, size: float = 9.5, style: str = "", color=INK, lh: float = 4.9, indent: float = 0):
    pdf.set_font("inter", style, size)
    pdf.set_text_color(*color)
    pdf.set_x(M + indent)
    pdf.multi_cell(W - 2 * M - indent, lh, txt, align="L", new_x="LMARGIN", new_y="NEXT")


def _block(pdf, b: dict) -> None:
    t = b.get("type")
    if t == "p":
        _text(pdf, b["text"])
        pdf.ln(2)
    elif t == "list":
        if pdf.get_y() > H - 16 - min(60, 8 + 7 * len(b["items"])):  # keep a short list (and its title) on one page
            pdf.add_page()
        if b.get("title"):
            pdf.ln(1)
            _text(pdf, b["title"], 10, "B")
            pdf.ln(0.5)
        for x in b["items"]:
            y = pdf.get_y()
            pdf.set_font("inter", "", 9.5)
            pdf.set_text_color(*ACC)
            pdf.set_xy(M, y)
            pdf.cell(4, 4.9, "•")
            _text(pdf, x, indent=4.5)
            pdf.ln(0.8)
        pdf.ln(1.5)
    elif t == "rows":
        for k, v in b["rows"]:
            _text(pdf, k, 7.8, "", MUT, 4)
            _text(pdf, v, 9.5, "B", INK, 4.8)
            pdf.set_draw_color(*LINE)
            pdf.line(M, pdf.get_y() + 1.2, W - M, pdf.get_y() + 1.2)
            pdf.ln(2.6)
        pdf.ln(1)
    elif t == "cards":
        for c in b["items"]:
            if pdf.get_y() > H - 45:
                pdf.add_page()
            _text(pdf, c["title"], 10, "B", INK, 5)
            if c.get("tag"):
                _text(pdf, c["tag"].upper(), 7.2, "B", TAG.get(c["tag"], ACC), 4)
            _text(pdf, c["text"], 9.3, "", INK, 4.8)
            if c.get("sub"):
                _text(pdf, c["sub"], 8, "", MUT, 4.2)
            pdf.set_draw_color(*LINE)
            pdf.line(M, pdf.get_y() + 1.5, W - M, pdf.get_y() + 1.5)
            pdf.ln(3.5)
    elif t == "qa":
        for x in b["items"]:
            pdf.set_fill_color(*ACC)
            y = pdf.get_y()
            _text(pdf, x["q"], 10, "B", INK, 5, indent=3)
            pdf.rect(M, y, 0.8, pdf.get_y() - y, "F")
            pdf.ln(1)
            for para in [p for p in x["a"].split("\n") if p.strip()]:
                _text(pdf, para.lstrip("-* ").strip(), 9.3, "", INK, 4.8, indent=3)
                pdf.ln(0.8)
            pdf.ln(3)


def render(book: dict) -> bytes:
    pdf = _pdf()
    # cover
    pdf.add_page()
    if LOGO.exists():
        pdf.image(str(LOGO), x=W / 2 - 11, y=38, w=22)
    pdf.set_y(70)
    pdf.set_font("inter", "B", 8)
    pdf.set_text_color(*ACC)
    pdf.cell(0, 5, "L I F E   B O O K", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("serif", "B", 30)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 12, book.get("title", "Life Book"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    made = book.get("made")
    when = date.fromisoformat(made).strftime("%-d %B %Y") if made else ""
    pdf.set_font("inter", "", 9.5)
    pdf.set_text_color(*MUT)
    pdf.multi_cell(0, 5.5, f"{book.get('lagna', '')} lagna\nMade {when}\nReviewed by your astrologer", align="C",
                   new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(H - 30)
    pdf.set_font("inter", "B", 10)
    pdf.set_text_color(*ACC)
    pdf.cell(0, 5, "simplejyotish.com", align="C")
    # contents
    chapters = book.get("chapters", [])
    pdf.add_page()
    pdf.set_font("serif", "B", 22)
    pdf.set_text_color(*INK)
    pdf.cell(0, 12, "Contents", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    for i, c in enumerate(chapters, 1):
        pdf.set_font("serif", "B", 13)
        pdf.set_text_color(*ACC)
        pdf.cell(9, 8, str(i))
        pdf.set_font("inter", "", 10)
        pdf.set_text_color(*INK)
        pdf.cell(0, 8, c["title"], new_x="LMARGIN", new_y="NEXT")
    # chapters
    for i, c in enumerate(chapters, 1):
        pdf.add_page()
        pdf.set_font("inter", "B", 7.5)
        pdf.set_text_color(*ACC)
        pdf.cell(0, 5, f"CHAPTER {i}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("serif", "B", 22)
        pdf.set_text_color(*INK)
        pdf.multi_cell(0, 9.5, c["title"], new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        if c.get("intro"):
            _text(pdf, c["intro"], 9.5, "", MUT)
            pdf.ln(3)
        for b in c.get("blocks", []):
            _block(pdf, b)
    return bytes(pdf.output())
