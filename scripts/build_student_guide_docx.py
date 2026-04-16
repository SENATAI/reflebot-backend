"""
Сборка красивого DOCX-файла из .docs/STUDENT_BOT_GUIDE.md.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape


ROOT_DIR = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT_DIR / ".docs" / "STUDENT_BOT_GUIDE.md"
OUTPUT_PATH = ROOT_DIR / ".docs" / "STUDENT_BOT_GUIDE.docx"


def build_docx(source_path: Path, output_path: Path) -> None:
    """Собрать DOCX-файл из markdown-инструкции."""
    lines = source_path.read_text(encoding="utf-8").splitlines()
    body = render_document_body(lines)

    document_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document "
        "xmlns:wpc=\"http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas\" "
        "xmlns:mc=\"http://schemas.openxmlformats.org/markup-compatibility/2006\" "
        "xmlns:o=\"urn:schemas-microsoft-com:office:office\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" "
        "xmlns:m=\"http://schemas.openxmlformats.org/officeDocument/2006/math\" "
        "xmlns:v=\"urn:schemas-microsoft-com:vml\" "
        "xmlns:wp14=\"http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing\" "
        "xmlns:wp=\"http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing\" "
        "xmlns:w10=\"urn:schemas-microsoft-com:office:word\" "
        "xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" "
        "xmlns:w14=\"http://schemas.microsoft.com/office/word/2010/wordml\" "
        "xmlns:wpg=\"http://schemas.microsoft.com/office/word/2010/wordprocessingGroup\" "
        "xmlns:wpi=\"http://schemas.microsoft.com/office/word/2010/wordprocessingInk\" "
        "xmlns:wne=\"http://schemas.microsoft.com/office/word/2006/wordml\" "
        "xmlns:wps=\"http://schemas.microsoft.com/office/word/2010/wordprocessingShape\" "
        "mc:Ignorable=\"w14 wp14\">"
        f"<w:body>{body}{section_properties()}</w:body>"
        "</w:document>"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml())
        archive.writestr("_rels/.rels", root_rels_xml())
        archive.writestr("docProps/core.xml", core_xml())
        archive.writestr("docProps/app.xml", app_xml())
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/styles.xml", styles_xml())
        archive.writestr("word/numbering.xml", numbering_xml())
        archive.writestr("word/settings.xml", settings_xml())
        archive.writestr("word/webSettings.xml", web_settings_xml())
        archive.writestr("word/fontTable.xml", font_table_xml())
        archive.writestr("word/theme/theme1.xml", theme_xml())
        archive.writestr("word/_rels/document.xml.rels", document_rels_xml())


def render_document_body(lines: list[str]) -> str:
    """Преобразовать markdown-линии в XML body DOCX."""
    parts: list[str] = []
    paragraph_buffer: list[str] = []

    def flush_paragraph() -> None:
        if not paragraph_buffer:
            return
        text = " ".join(part.strip() for part in paragraph_buffer if part.strip())
        paragraph_buffer.clear()
        if not text:
            return
        if text.startswith("`") and text.endswith("`") and len(text) > 1:
            parts.append(paragraph(text.strip("`"), style="Callout"))
            return
        parts.append(paragraph(text))

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            continue

        if stripped.startswith("# "):
            flush_paragraph()
            parts.append(paragraph(stripped[2:].strip(), style="Title"))
            parts.append(paragraph("Инструкция для студентов", style="Subtitle"))
            continue

        if stripped.startswith("## "):
            flush_paragraph()
            parts.append(paragraph(stripped[3:].strip(), style="Heading1"))
            continue

        if stripped.startswith("### "):
            flush_paragraph()
            parts.append(paragraph(stripped[4:].strip(), style="Heading2"))
            continue

        bullet_match = re.match(r"^- (.+)$", stripped)
        if bullet_match:
            flush_paragraph()
            parts.append(list_paragraph(clean_inline_markup(bullet_match.group(1)), numbered=False))
            continue

        numbered_match = re.match(r"^\d+\. (.+)$", stripped)
        if numbered_match:
            flush_paragraph()
            parts.append(list_paragraph(clean_inline_markup(numbered_match.group(1)), numbered=True))
            continue

        paragraph_buffer.append(clean_inline_markup(stripped))

    flush_paragraph()
    return "".join(parts)


def clean_inline_markup(text: str) -> str:
    """Упростить inline markdown для Word-документа."""
    return text.replace("`", "")


def paragraph(text: str, *, style: str = "Body") -> str:
    """Построить XML обычного абзаца."""
    return (
        "<w:p>"
        f"<w:pPr><w:pStyle w:val=\"{style}\"/></w:pPr>"
        f"<w:r><w:t xml:space=\"preserve\">{xml_escape(text)}</w:t></w:r>"
        "</w:p>"
    )


def list_paragraph(text: str, *, numbered: bool) -> str:
    """Построить XML абзаца списка."""
    num_id = "2" if numbered else "1"
    return (
        "<w:p>"
        "<w:pPr>"
        "<w:pStyle w:val=\"Body\"/>"
        f"<w:numPr><w:ilvl w:val=\"0\"/><w:numId w:val=\"{num_id}\"/></w:numPr>"
        "</w:pPr>"
        f"<w:r><w:t xml:space=\"preserve\">{xml_escape(text)}</w:t></w:r>"
        "</w:p>"
    )


def section_properties() -> str:
    """Параметры страницы документа."""
    return (
        "<w:sectPr>"
        "<w:pgSz w:w=\"11906\" w:h=\"16838\"/>"
        "<w:pgMar w:top=\"992\" w:right=\"992\" w:bottom=\"992\" w:left=\"992\" "
        "w:header=\"708\" w:footer=\"708\" w:gutter=\"0\"/>"
        "</w:sectPr>"
    )


def content_types_xml() -> str:
    """Content types для DOCX."""
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
  <Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
  <Override PartName="/word/webSettings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.webSettings+xml"/>
  <Override PartName="/word/fontTable.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"/>
  <Override PartName="/word/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
</Types>"""


def root_rels_xml() -> str:
    """Root relationships для DOCX."""
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""


def document_rels_xml() -> str:
    """Relationships внутри word/document.xml."""
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
  <Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/webSettings" Target="webSettings.xml"/>
  <Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable" Target="fontTable.xml"/>
  <Relationship Id="rId6" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>
</Relationships>"""


def core_xml() -> str:
    """Core metadata."""
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:dcmitype="http://purl.org/dc/dcmitype/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>Student Bot Guide</dc:title>
  <dc:subject>Reflebot</dc:subject>
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
</cp:coreProperties>"""


def app_xml() -> str:
    """Extended metadata."""
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
 xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Codex</Application>
</Properties>"""


def styles_xml() -> str:
    """Стили документа."""
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Aptos" w:hAnsi="Aptos" w:cs="Aptos"/>
        <w:sz w:val="22"/>
        <w:szCs w:val="22"/>
        <w:lang w:val="ru-RU"/>
      </w:rPr>
    </w:rPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Body">
    <w:name w:val="Body"/>
    <w:qFormat/>
    <w:pPr>
      <w:spacing w:after="120" w:line="300" w:lineRule="auto"/>
    </w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:basedOn w:val="Body"/>
    <w:qFormat/>
    <w:pPr>
      <w:jc w:val="center"/>
      <w:spacing w:before="120" w:after="120"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:color w:val="1F4E79"/>
      <w:sz w:val="34"/>
      <w:szCs w:val="34"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle">
    <w:name w:val="Subtitle"/>
    <w:basedOn w:val="Body"/>
    <w:qFormat/>
    <w:pPr>
      <w:jc w:val="center"/>
      <w:spacing w:after="240"/>
    </w:pPr>
    <w:rPr>
      <w:i/>
      <w:color w:val="5B7083"/>
      <w:sz w:val="22"/>
      <w:szCs w:val="22"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="Heading 1"/>
    <w:basedOn w:val="Body"/>
    <w:qFormat/>
    <w:pPr>
      <w:spacing w:before="240" w:after="120"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:color w:val="1F4E79"/>
      <w:sz w:val="28"/>
      <w:szCs w:val="28"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="Heading 2"/>
    <w:basedOn w:val="Body"/>
    <w:qFormat/>
    <w:pPr>
      <w:spacing w:before="180" w:after="80"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:color w:val="2F5597"/>
      <w:sz w:val="24"/>
      <w:szCs w:val="24"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Callout">
    <w:name w:val="Callout"/>
    <w:basedOn w:val="Body"/>
    <w:pPr>
      <w:spacing w:before="80" w:after="80"/>
      <w:ind w:left="240" right="120"/>
      <w:shd w:val="clear" w:color="auto" w:fill="EAF2F8"/>
      <w:pBdr>
        <w:left w:val="single" w:sz="12" w:space="0" w:color="4F81BD"/>
      </w:pBdr>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:color w:val="1F1F1F"/>
    </w:rPr>
  </w:style>
</w:styles>"""


def numbering_xml() -> str:
    """Нумерация и маркеры."""
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="0">
    <w:multiLevelType w:val="hybridMultilevel"/>
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/>
      <w:numFmt w:val="bullet"/>
      <w:lvlText w:val="•"/>
      <w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>
      <w:rPr><w:rFonts w:ascii="Aptos" w:hAnsi="Aptos"/></w:rPr>
    </w:lvl>
  </w:abstractNum>
  <w:abstractNum w:abstractNumId="1">
    <w:multiLevelType w:val="hybridMultilevel"/>
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/>
      <w:numFmt w:val="decimal"/>
      <w:lvlText w:val="%1."/>
      <w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>
    </w:lvl>
  </w:abstractNum>
  <w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
  <w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>
</w:numbering>"""


def settings_xml() -> str:
    """Настройки документа."""
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:zoom w:percent="110"/>
  <w:defaultTabStop w:val="720"/>
</w:settings>"""


def web_settings_xml() -> str:
    """Web settings."""
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:webSettings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>"""


def font_table_xml() -> str:
    """Таблица шрифтов."""
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:fonts xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:font w:name="Aptos">
    <w:panose1 w:val="020F0302020204030204"/>
    <w:charset w:val="CC"/>
    <w:family w:val="swiss"/>
    <w:pitch w:val="variable"/>
  </w:font>
</w:fonts>"""


def theme_xml() -> str:
    """Минимальная тема документа."""
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Codex Theme">
  <a:themeElements>
    <a:clrScheme name="Codex">
      <a:dk1><a:srgbClr val="1F1F1F"/></a:dk1>
      <a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="1F4E79"/></a:dk2>
      <a:lt2><a:srgbClr val="EAF2F8"/></a:lt2>
      <a:accent1><a:srgbClr val="2F5597"/></a:accent1>
      <a:accent2><a:srgbClr val="5B9BD5"/></a:accent2>
      <a:accent3><a:srgbClr val="70AD47"/></a:accent3>
      <a:accent4><a:srgbClr val="FFC000"/></a:accent4>
      <a:accent5><a:srgbClr val="ED7D31"/></a:accent5>
      <a:accent6><a:srgbClr val="A5A5A5"/></a:accent6>
      <a:hlink><a:srgbClr val="0563C1"/></a:hlink>
      <a:folHlink><a:srgbClr val="954F72"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="Codex Fonts">
      <a:majorFont><a:latin typeface="Aptos"/></a:majorFont>
      <a:minorFont><a:latin typeface="Aptos"/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="Codex Format"/>
  </a:themeElements>
</a:theme>"""


if __name__ == "__main__":
    build_docx(SOURCE_PATH, OUTPUT_PATH)
    print(OUTPUT_PATH)
