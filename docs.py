"""Minimal Word (.docx) engine using only the standard library.

A .docx file is a zip of XML parts. Buddy writes real, valid Word documents
(title, headings, paragraphs, bullets, tables) and reads them back, with no
third-party packages. Documents produced here open in Word, Google Docs and
LibreOffice.
"""
import os
import re
import zipfile
from xml.sax.saxutils import escape

from tools import ToolError

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>"""

STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="24"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:sz w:val="56"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:before="360" w:after="120"/></w:pPr><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:before="240" w:after="80"/></w:pPr><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="ListBullet"><w:name w:val="List Bullet"/><w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:ind w:left="720"/></w:pPr></w:style></w:styles>"""


def _para(style, text):
    return (f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>'
            f'<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>')


def _bullet(text):
    return (f'<w:p><w:pPr><w:pStyle w:val="ListBullet"/></w:pPr>'
            f'<w:r><w:t xml:space="preserve">\u2022  {escape(text)}</w:t></w:r></w:p>')


def _table(rows):
    borders = ("<w:tblBorders><w:top w:val=\"single\" w:sz=\"4\"/>"
               "<w:left w:val=\"single\" w:sz=\"4\"/>"
               "<w:bottom w:val=\"single\" w:sz=\"4\"/>"
               "<w:right w:val=\"single\" w:sz=\"4\"/>"
               "<w:insideH w:val=\"single\" w:sz=\"4\"/>"
               "<w:insideV w:val=\"single\" w:sz=\"4\"/></w:tblBorders>")
    out = [f"<w:tbl><w:tblPr>{borders}</w:tblPr>"]
    for row in rows:
        out.append("<w:tr>")
        for cell in row:
            out.append(f"<w:tc><w:p><w:r><w:t xml:space=\"preserve\">"
                       f"{escape(str(cell))}</w:t></w:r></w:p></w:tc>")
        out.append("</w:tr>")
    out.append("</w:tbl>")
    return "".join(out)


def build_document(blocks, path):
    """blocks: list of (kind, value). kind in title/heading/paragraph/bullet/table."""
    body = []
    for kind, value in blocks:
        if kind == "title":
            body.append(_para("Title", value))
        elif kind == "heading":
            body.append(_para("Heading1", value))
        elif kind == "heading2":
            body.append(_para("Heading2", value))
        elif kind == "bullet":
            body.append(_bullet(value))
        elif kind == "table":
            body.append(_table(value))
        else:
            body.append(_para("Normal", value))
    document = ("""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">"""
                f"<w:body>{''.join(body)}</w:body></w:document>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", document)
        z.writestr("word/styles.xml", STYLES)
    return path


def read_document_blocks(path):
    """Return [(style, text)] for each paragraph in a .docx file."""
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8")
    except (OSError, KeyError, zipfile.BadZipFile):
        raise ToolError("That doesn't look like a Word document I can read.")
    blocks = []
    for para in re.findall(r"<w:p\b.*?</w:p>", xml, flags=re.DOTALL):
        style_m = re.search(r'<w:pStyle w:val="([^"]+)"', para)
        style = style_m.group(1) if style_m else "Normal"
        texts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", para, flags=re.DOTALL)
        text = "".join(texts)
        if text.strip():
            blocks.append((style, text))
    return blocks


def read_document_text(path):
    blocks = read_document_blocks(path)
    if not blocks:
        raise ToolError("That Word document seems to be empty.")
    return "\n".join(text for _, text in blocks)


def append_to_document(path, new_blocks):
    blocks = read_document_blocks(path)
    style_map = {"title": "Title", "heading": "Heading1", "heading2": "Heading2",
                 "bullet": "ListBullet", "paragraph": "Normal"}
    for kind, value in new_blocks:
        if kind == "table":
            blocks.append(("Table", value))
        else:
            blocks.append((style_map.get(kind, "Normal"), value))
    # Rebuild preserving styles; tables are re-added at the end as new tables.
    body = []
    for style, value in blocks:
        if style == "Table":
            body.append(_table(value))
        elif style == "ListBullet":
            body.append(_bullet(value.replace("\u2022  ", "", 1)))
        else:
            body.append(_para(style, value))
    document = ("""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">"""
                f"<w:body>{''.join(body)}</w:body></w:document>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", document)
        z.writestr("word/styles.xml", STYLES)
    return path


def text_to_blocks(text):
    """Small Markdown subset: '# ' headings, '- ' bullets, plain paragraphs."""
    blocks = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("## "):
            blocks.append(("heading2", line[3:].strip()))
        elif line.startswith("# "):
            blocks.append(("heading", line[2:].strip()))
        elif line.startswith(("- ", "* ")):
            blocks.append(("bullet", line[2:].strip()))
        else:
            blocks.append(("paragraph", line))
    return blocks or [("paragraph", text)]
