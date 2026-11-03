"""Exercise PDF, Pandoc DOCX, and bounded text extraction."""

import shutil
from io import BytesIO
from pathlib import Path

import pypandoc
import pytest
from reportlab.pdfgen import canvas

from app.core.exceptions import BusinessError
from app.services.file_parse_service import parse_file


def test_text_is_split_into_bounded_fragments() -> None:
    text = "\n".join(f"Line {index}: long context for Agent experiments." for index in range(200))
    parsed = parse_file("notes.md", text.encode("utf-8"))
    assert parsed.text_chars == len(text)
    assert len(parsed.fragments) > 1
    assert all(len(fragment) <= 2500 for fragment in parsed.fragments)
    assert "Line 0" in parsed.fragments[0]
    assert "Line 199" in parsed.fragments[-1]


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="Pandoc executable is required")
def test_docx_uses_local_pandoc(tmp_path: Path) -> None:
    source = tmp_path / "sample.docx"
    pypandoc.convert_text("# Heading\n\n- First item\n- Second item", to="docx", format="md", outputfile=str(source))
    parsed = parse_file("sample.docx", source.read_bytes())
    assert parsed.extension == ".docx"
    content = "\n".join(parsed.fragments)
    assert "Heading" in content and "First item" in content and "Second item" in content


def test_pdf_text_includes_page_markers() -> None:
    output = BytesIO()
    pdf = canvas.Canvas(output)
    pdf.drawString(72, 750, "Page one content")
    pdf.showPage()
    pdf.drawString(72, 750, "Page two content")
    pdf.save()
    parsed = parse_file("sample.pdf", output.getvalue())
    content = "\n".join(parsed.fragments)
    assert "[第 1 页]" in content and "Page one content" in content
    assert "[第 2 页]" in content and "Page two content" in content


def test_invalid_pdf_is_rejected_before_upload() -> None:
    with pytest.raises(BusinessError) as caught:
        parse_file("bad.pdf", b"not a PDF")
    assert caught.value.status == 422
