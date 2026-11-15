"""Excel (.xlsx), PowerPoint (.pptx) and PDF reading, standard library only.

Both Office formats are zip packages of XML, like .docx. The writers produce
small but valid files (LibreOffice converts them cleanly). The PDF reader is
best-effort: it extracts text from ordinary PDFs and says so honestly when
a file's text cannot be extracted.
"""
import re
import zipfile
import zlib
from xml.sax.saxutils import escape

from tools import ToolError

# ------------------------------------------------------------------ xlsx

def _col_letter(n):
    letters = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


XLSX_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>"""

XLSX_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>"""

XLSX_WORKBOOK = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>"""

XLSX_WORKBOOK_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>"""

XLSX_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts><font><sz val="11"/><name val="Calibri"/></font></fonts><fills><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders><border/></borders><cellStyleXfs><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs><cellStyles><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>"""


def build_spreadsheet(headers, rows, path):
    """headers: list[str], rows: list[list]. Values starting with '=' become formulas."""
    strings, index = [], {}

    def sidx(value):
        if value not in index:
            index[value] = len(strings)
            strings.append(value)
        return index[value]

    sheet_rows = []
    all_rows = ([headers] if headers else []) + rows
    for ri, row in enumerate(all_rows, start=1):
        cells = []
        for ci, value in enumerate(row):
            ref = f"{_col_letter(ci + 1)}{ri}"
            if isinstance(value, str) and value.startswith("="):
                cells.append(f'<c r="{ref}"><f>{escape(value[1:])}</f></c>')
            elif isinstance(value, (int, float)):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="s"><v>{sidx(str(value))}</v></c>')
        sheet_rows.append(f'<row r="{ri}">{"".join(cells)}</row>')
    sheet = ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
             "<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">"
             f"<sheetData>{''.join(sheet_rows)}</sheetData></worksheet>")
    sst = ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
           "<sst xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" "
           f"count=\"{len(strings)}\" uniqueCount=\"{len(strings)}\">"
           + "".join(f"<si><t xml:space=\"preserve\">{escape(s)}</t></si>"
                     for s in strings) + "</sst>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", XLSX_CONTENT_TYPES)
        z.writestr("_rels/.rels", XLSX_RELS)
        z.writestr("xl/workbook.xml", XLSX_WORKBOOK)
        z.writestr("xl/_rels/workbook.xml.rels", XLSX_WORKBOOK_RELS)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
        z.writestr("xl/sharedStrings.xml", sst)
        z.writestr("xl/styles.xml", XLSX_STYLES)
    return path


def read_spreadsheet_rows(path):
    try:
        with zipfile.ZipFile(path) as z:
            sheet = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
            try:
                shared = z.read("xl/sharedStrings.xml").decode("utf-8")
                strings = re.findall(r"<si>(.*?)</si>", shared, flags=re.DOTALL)
                strings = [re.sub(r"<[^>]+>", "", s) for s in strings]
            except KeyError:
                strings = []
    except (OSError, KeyError, zipfile.BadZipFile):
        raise ToolError("That doesn't look like a spreadsheet I can read.")
    rows = []
    for row_xml in re.findall(r"<row\b.*?</row>", sheet, flags=re.DOTALL):
        row = []
        for cell in re.findall(r"<c\b.*?</c>", row_xml, flags=re.DOTALL):
            f = re.search(r"<f>(.*?)</f>", cell)
            if f:
                row.append("=" + f.group(1))
                continue
            v = re.search(r"<v>(.*?)</v>", cell)
            if v is None:
                row.append("")
            elif 't="s"' in cell:
                try:
                    row.append(strings[int(v.group(1))])
                except (ValueError, IndexError):
                    row.append("")
            else:
                row.append(v.group(1))
        rows.append(row)
    return rows


def read_spreadsheet_text(path):
    rows = read_spreadsheet_rows(path)
    if not rows:
        raise ToolError("That spreadsheet seems to be empty.")
    return "\n".join(" | ".join(cells) for cells in rows)


# ------------------------------------------------------------------ pptx

PPTX_THEME = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office Theme"><a:themeElements><a:clrScheme name="Office"><a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1><a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="1F497D"/></a:dk2><a:lt2><a:srgbClr val="EEECE1"/></a:lt2><a:accent1><a:srgbClr val="4F81BD"/></a:accent1><a:accent2><a:srgbClr val="C0504D"/></a:accent2><a:accent3><a:srgbClr val="9BBB59"/></a:accent3><a:accent4><a:srgbClr val="8064A2"/></a:accent4><a:accent5><a:srgbClr val="4BACC6"/></a:accent5><a:accent6><a:srgbClr val="F79646"/></a:accent6><a:hlink><a:srgbClr val="0000FF"/></a:hlink><a:folHlink><a:srgbClr val="800080"/></a:folHlink></a:clrScheme><a:fontScheme name="Office"><a:majorFont><a:latin typeface="Calibri"/></a:majorFont><a:minorFont><a:latin typeface="Calibri"/></a:minorFont></a:fontScheme><a:fmtScheme name="Office"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme></a:themeElements></a:theme>"""

PPTX_MASTER = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></p:bgPr></p:bg><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/><p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles><p:titleStyle><a:lvl1pPr algn="l"><a:defRPr sz="3200"/></a:lvl1pPr></p:titleStyle><p:bodyStyle><a:lvl1pPr algn="l"><a:defRPr sz="2400"/></a:lvl1pPr></p:bodyStyle><p:otherStyle><a:lvl1pPr algn="l"><a:defRPr sz="1800"/></a:lvl1pPr></p:otherStyle></p:txStyles></p:sldMaster>"""

PPTX_LAYOUT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank"><p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>"""


def _pptx_textbox(shape_id, x, y, cx, cy, runs):
    """runs: list of (text, size_hundredths_of_point, bold)."""
    paras = []
    for text, size, bold in runs:
        b = "<a:b val=\"1\"/>" if bold else ""
        paras.append(f"<a:p><a:r><a:rPr lang=\"en-US\" sz=\"{size}\">{b}</a:rPr>"
                     f"<a:t>{escape(text)}</a:t></a:r></a:p>")
    return (f"<p:sp><p:nvSpPr><p:cNvPr id=\"{shape_id}\" name=\"\"/>"
            f"<p:cNvSpPr><a:spLocks noGrp=\"1\"/></p:cNvSpPr><p:nvPr/></p:nvSpPr>"
            f"<p:spPr><a:xfrm><a:off x=\"{x}\" y=\"{y}\"/><a:ext cx=\"{cx}\" cy=\"{cy}\"/>"
            f"</a:xfrm><a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom></p:spPr>"
            f"<p:txBody><a:bodyPr wrap=\"square\"/><a:lstStyle/>"
            f"{''.join(paras)}</p:txBody></p:sp>")


def _pptx_slide(title, bullets):
    shapes = [_pptx_textbox(2, 457200, 274638, 8229600, 1143000,
                            [(title, 3200, True)])]
    if bullets:
        runs = [(f"\u2022  {b}", 2000, False) for b in bullets]
        shapes.append(_pptx_textbox(3, 457200, 1600200, 8229600, 4000000, runs))
    return ("""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>"""
            + "".join(shapes) +
            """</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>""")


def build_presentation(slides, path):
    """slides: list of (title, [bullet, ...]). First slide is the title slide."""
    n = len(slides)
    sld_ids = "".join(
        f'<p:sldId id="{256 + i}" r:id="rId{2 + i}"/>' for i in range(n))
    presentation = ("""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>"""
                    f"<p:sldIdLst>{sld_ids}</p:sldIdLst>"
                    """<p:sldSz cx="9144000" cy="6858000"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>""")
    pres_rels = ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
                 "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
                 "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster\" Target=\"slideMasters/slideMaster1.xml\"/>"
                 + "".join(
                     f"<Relationship Id=\"rId{2 + i}\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide\" Target=\"slides/slide{i + 1}.xml\"/>"
                     for i in range(n)) +
                 "<Relationship Id=\"rId99\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme\" Target=\"theme/theme1.xml\"/>"
                 "</Relationships>")
    content_types = ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
                     "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
                     "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
                     "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
                     "<Override PartName=\"/ppt/presentation.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml\"/>"
                     + "".join(
                         f"<Override PartName=\"/ppt/slides/slide{i + 1}.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.slide+xml\"/>"
                         for i in range(n)) +
                     "<Override PartName=\"/ppt/slideMasters/slideMaster1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml\"/>"
                     "<Override PartName=\"/ppt/slideLayouts/slideLayout1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml\"/>"
                     "<Override PartName=\"/ppt/theme/theme1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.theme+xml\"/>"
                     "</Types>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels",
                   """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/></Relationships>""")
        z.writestr("ppt/presentation.xml", presentation)
        z.writestr("ppt/_rels/presentation.xml.rels", pres_rels)
        z.writestr("ppt/slideMasters/slideMaster1.xml", PPTX_MASTER)
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels",
                   """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/></Relationships>""")
        z.writestr("ppt/slideLayouts/slideLayout1.xml", PPTX_LAYOUT)
        z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels",
                   """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>""")
        z.writestr("ppt/theme/theme1.xml", PPTX_THEME)
        for i, (title, bullets) in enumerate(slides):
            z.writestr(f"ppt/slides/slide{i + 1}.xml", _pptx_slide(title, bullets))
            z.writestr(f"ppt/slides/_rels/slide{i + 1}.xml.rels",
                       """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/></Relationships>""")
    return path


# ------------------------------------------------------------------ pdf

def _pdf_stream(obj_body):
    """Decompressed bytes of an object's stream, or b'' if there is none."""
    m = re.search(rb"stream\r?\n(.*?)endstream", obj_body, re.DOTALL)
    if not m:
        return b""
    raw = m.group(1).strip(b"\r\n")
    try:
        return zlib.decompress(raw)
    except zlib.error:
        return raw


def _pdf_decode_dst(raw):
    """A ToUnicode destination string -> unicode text."""
    try:
        if len(raw) >= 2 and len(raw) % 2 == 0:
            text = raw.decode("utf-16-be")
            if all(32 <= ord(c) < 127 or c in "\n\t\r" for c in text):
                return text
    except UnicodeDecodeError:
        pass
    return raw.decode("latin-1", "replace")


def _parse_cmap(stream):
    """Parse a ToUnicode CMap stream -> ({code: char}, {code lengths})."""
    cmap, lengths = {}, set()
    for body in re.findall(rb"begincodespacerange\s*(.*?)endcodespacerange",
                           stream, re.DOTALL):
        for a, b in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", body):
            lengths.add(len(bytes.fromhex(a.decode("ascii"))))
    for body in re.findall(rb"beginbfchar\s*(.*?)endbfchar", stream, re.DOTALL):
        for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", body):
            cmap[int(src, 16)] = _pdf_decode_dst(bytes.fromhex(dst.decode("ascii")))
    for body in re.findall(rb"beginbfrange\s*(.*?)endbfrange", stream, re.DOTALL):
        for lo, hi, dst in re.findall(
                rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", body):
            start, end = int(lo, 16), int(hi, 16)
            base = bytes.fromhex(dst.decode("ascii"))
            width = max(1, len(base))
            base_int = int.from_bytes(base, "big")
            for i, code in enumerate(range(start, end + 1)):
                try:
                    cmap[code] = _pdf_decode_dst(
                        (base_int + i).to_bytes(width, "big"))
                except OverflowError:
                    cmap[code] = _pdf_decode_dst(base)
        for lo, hi, arr in re.findall(
                rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*\[(.*?)\]",
                body, re.DOTALL):
            start = int(lo, 16)
            for i, dst in enumerate(re.findall(rb"<([0-9A-Fa-f]+)>", arr)):
                cmap[start + i] = _pdf_decode_dst(
                    bytes.fromhex(dst.decode("ascii")))
    return cmap, lengths


def _pdf_literal(raw):
    s = raw.decode("latin-1", "replace")
    return (s.replace("\\(", "(").replace("\\)", ")")
             .replace("\\\\", "\\").replace("\\n", "\n"))


def read_pdf_text(path):
    """Extract text from a PDF using its content streams and ToUnicode maps.

    Handles the common cases: simple fonts (literal strings) and embedded
    subset fonts (hex strings + ToUnicode CMap). Raises ToolError when the
    file's text genuinely cannot be extracted (e.g. scanned images).
    """
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        raise ToolError(f"I can't find a file at {path}.")
    if not data.startswith(b"%PDF"):
        raise ToolError("That doesn't look like a PDF file.")
    objs = {}
    for m in re.finditer(rb"(\d+) 0 obj(.*?)endobj", data, re.DOTALL):
        objs[int(m.group(1))] = m.group(2)

    # ToUnicode maps, keyed by their object number.
    cmaps = {}
    for num, body in objs.items():
        stream = _pdf_stream(body)
        if b"beginbfchar" in stream or b"beginbfrange" in stream:
            cmaps[num] = _parse_cmap(stream)
    # Font name -> font object, and font object -> its ToUnicode map object.
    # (Resources may reference the font dict indirectly, so scan all objects.)
    font_ref_by_name = {}
    tounicode_by_font = {}
    for num, body in objs.items():
        for name, ref in re.findall(rb"/(F\w+)\s+(\d+) 0 R", body):
            font_ref_by_name[name.decode("latin-1")] = int(ref)
        m = re.search(rb"/ToUnicode\s+(\d+) 0 R", body)
        if m:
            tounicode_by_font[num] = int(m.group(1))
    # Page content streams.
    contents = []
    for body in objs.values():
        if b"/Type" in body and re.search(rb"/Type\s*/Page[^s]", body):
            for ref in re.findall(rb"/Contents\s+(\d+) 0 R", body):
                contents.append(int(ref))
            for arr in re.findall(rb"/Contents\s*\[(.*?)\]", body, re.DOTALL):
                contents.extend(int(r) for r in
                                re.findall(rb"(\d+) 0 R", arr))
    if not contents:
        raise ToolError("I couldn't find any readable text in that PDF — it "
                        "may be scanned images, which need OCR software.")

    pieces = []
    token_re = re.compile(
        rb"/(F\w+)\s+[\d.]+\s+Tf"
        rb"|(\((?:[^()\\]|\\.)*\))\s*Tj"
        rb"|<([0-9A-Fa-f\s]+)>\s*Tj"
        rb"|\[(.*?)\]\s*TJ"
        rb"|BT"
        rb"|([\d.\-]+)\s+([\d.\-]+)\s+Td"
        rb"|([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+Tm"
        rb"|T\*", re.DOTALL)
    for ref in contents:
        stream = _pdf_stream(objs.get(ref, b""))
        if not stream:
            continue
        current = None
        for m in token_re.finditer(stream):
            if m.group(1):
                current = m.group(1).decode("latin-1")
                continue
            # Line breaks: a new text block or a move to a new line.
            if m.group(0) in (b"BT", b"T*") or m.group(0).endswith((b"Td", b"Tm")):
                if pieces and not pieces[-1].endswith("\n"):
                    pieces.append("\n")
                continue
            cmap, lengths = None, set()
            if current and current in font_ref_by_name:
                cmap_ref = tounicode_by_font.get(font_ref_by_name[current])
                if cmap_ref is not None:
                    cmap, lengths = cmaps.get(cmap_ref, ({}, set()))
            strings = []
            if m.group(2):
                strings.append(("lit", m.group(2)[1:-1]))
            elif m.group(3):
                hx = re.sub(rb"\s", b"", m.group(3))
                if len(hx) % 2 == 0:
                    strings.append(("hex", bytes.fromhex(hx.decode("ascii"))))
            elif m.group(4):
                arr = m.group(4)
                for lit in re.findall(rb"\((?:[^()\\]|\\.)*\)", arr):
                    strings.append(("lit", lit[1:-1]))
                for hx in re.findall(rb"<([0-9A-Fa-f\s]+)>", arr):
                    hx = re.sub(rb"\s", b"", hx)
                    if len(hx) % 2 == 0:
                        strings.append(("hex", bytes.fromhex(hx.decode("ascii"))))
            for kind, raw in strings:
                if cmap:
                    step = 2 if (lengths == {2} or
                                 any(c > 255 for c in cmap)) else 1
                    out = []
                    i = 0
                    while i < len(raw):
                        code = int.from_bytes(raw[i:i + step], "big")
                        out.append(cmap.get(code, ""))
                        i += step
                    pieces.append("".join(out))
                elif kind == "lit":
                    pieces.append(_pdf_literal(raw))
                else:
                    pieces.append(raw.decode("latin-1", "replace"))
    # Glyphs inside one show-operation join with nothing (word gaps are
    # real space glyphs); line breaks come from BT/Td/Tm/T* above.
    text = "".join(pieces)
    lines = [" ".join(line.split()) for line in text.split("\n")]
    text = "\n".join(ln for ln in lines if ln).strip()
    if not text:
        raise ToolError("I couldn't extract text from that PDF — it may be "
                        "scanned images, which need OCR software.")
    return text
