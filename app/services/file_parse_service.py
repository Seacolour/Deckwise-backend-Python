"""Extract bounded, page-friendly text from project uploads."""

import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import pypandoc
from langchain_text_splitters import RecursiveCharacterTextSplitter
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_TEXT_CHARS = 1_000_000
MAX_PDF_PAGES = 300
MAX_FRAGMENTS = 500
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=2_500, chunk_overlap=200,
    separators=["\n\n", "\n", "。", " ", ""],
)
_MIME = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".markdown": "text/markdown; charset=utf-8",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
_IMAGE_FORMATS = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP", ".gif": "GIF"}


@dataclass(frozen=True)
class ParsedFile:
    mime_type: str
    extension: str
    fragments: list[str]
    text_chars: int


def safe_filename(raw_name: str | None) -> str:
    name = Path((raw_name or "").replace("\\", "/")).name.strip()
    if not name or name in {".", ".."}:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "文件名无效")
    return name[:180]


def parse_file(filename: str, data: bytes) -> ParsedFile:
    if not data:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "文件内容为空")
    if len(data) > MAX_FILE_BYTES:
        raise BusinessError(413, ErrorCode.PARAMS_ERROR, "文件不能超过 50 MB")
    extension = Path(filename).suffix.lower()
    if extension not in _MIME:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "仅支持 PDF、DOCX、TXT、Markdown、JSON 和常见图片")

    if extension in _IMAGE_FORMATS:
        if len(data) > MAX_IMAGE_BYTES:
            raise BusinessError(413, ErrorCode.PARAMS_ERROR, "图片不能超过 8 MB")
        try:
            with Image.open(BytesIO(data)) as image:
                if image.format != _IMAGE_FORMATS[extension] or image.width * image.height > MAX_IMAGE_PIXELS:
                    raise ValueError("image format or dimensions invalid")
                image.verify()
        except (OSError, ValueError, UnidentifiedImageError) as error:
            raise BusinessError(422, ErrorCode.PARAMS_ERROR, "图片格式无效或尺寸过大") from error
        return ParsedFile(_MIME[extension], extension, [], 0)

    try:
        if extension == ".pdf":
            if not data.startswith(b"%PDF-"):
                raise ValueError("PDF signature missing")
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted:
                raise ValueError("encrypted PDF")
            if len(reader.pages) > MAX_PDF_PAGES:
                raise BusinessError(400, ErrorCode.PARAMS_ERROR, "PDF 页数超过 300 页")
            text = "\n\n".join(
                f"[第 {index} 页]\n{page_text}"
                for index, page in enumerate(reader.pages, start=1)
                if (page_text := (page.extract_text() or "").strip())
            )
        elif extension == ".docx":
            with TemporaryDirectory(prefix="deckwise-pandoc-") as directory:
                source = Path(directory) / "source.docx"
                source.write_bytes(data)
                text = pypandoc.convert_file(str(source), to="gfm", format="docx", extra_args=["--wrap=none"])
            text = re.sub(r"!\[[^]]*\]\([^)]*\)", "[嵌入图片]", text)
        else:
            text = data.decode("utf-8-sig")
    except BusinessError:
        raise
    except Exception as error:
        raise BusinessError(422, ErrorCode.PARAMS_ERROR, "文件解析失败，请检查格式或编码") from error

    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise BusinessError(422, ErrorCode.PARAMS_ERROR, "未提取到文本；扫描版 PDF 暂不支持 OCR")
    if len(text) > MAX_TEXT_CHARS:
        raise BusinessError(413, ErrorCode.PARAMS_ERROR, "解析文本超过当前 100 万字符限制")
    fragments = _SPLITTER.split_text(text)
    if not fragments or len(fragments) > MAX_FRAGMENTS:
        raise BusinessError(413, ErrorCode.PARAMS_ERROR, "文件分片数量超出当前限制")
    return ParsedFile(_MIME[extension], extension, fragments, len(text))
