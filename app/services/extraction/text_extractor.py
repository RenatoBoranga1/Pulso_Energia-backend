from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image
import pdfplumber
import pypdfium2
import pytesseract

from app.core.config import Settings
from app.core.enums import DocumentFileType
from app.core.errors import AppError
from app.models.uploaded_document import UploadedDocument
from app.services.documents.storage import LocalDocumentStorageService
from app.services.extraction.types import TextExtractionResult


class DocumentTextExtractionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.storage_service = LocalDocumentStorageService(settings)
        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    def extract(self, document: UploadedDocument) -> TextExtractionResult:
        path = self.storage_service.resolve(document.file_path)
        if not path.exists():
            raise AppError(
                "Stored document file was not found.",
                code="document_file_missing",
                status_code=404,
            )

        if document.file_type == DocumentFileType.PDF:
            return self._extract_from_pdf(path)

        if document.file_type in {DocumentFileType.JPG, DocumentFileType.JPEG, DocumentFileType.PNG}:
            text = self._extract_image_text(Image.open(path))
            return TextExtractionResult(text=text, method="ocr_image")

        raise AppError("Unsupported document type.", code="unsupported_document_type", status_code=400)

    def _extract_from_pdf(self, path: Path) -> TextExtractionResult:
        with pdfplumber.open(path) as pdf:
            page_texts = [(page.extract_text() or "").strip() for page in pdf.pages]
        native_text = "\n".join(text for text in page_texts if text).strip()

        if native_text:
            return TextExtractionResult(text=native_text, method="pdf_native")

        warnings = ["PDF did not contain extractable native text. Falling back to OCR."]
        text = self._extract_pdf_text_via_ocr(path)
        return TextExtractionResult(text=text, method="pdf_ocr", warnings=warnings)

    def _extract_pdf_text_via_ocr(self, path: Path) -> str:
        self._ensure_tesseract_available()

        document = pypdfium2.PdfDocument(str(path))
        try:
            page_texts: list[str] = []
            for page_index in range(len(document)):
                page = document.get_page(page_index)
                bitmap = page.render(scale=2)
                pil_image = bitmap.to_pil()
                page_texts.append(self._extract_image_text(pil_image))
                page.close()
            return "\n".join(text for text in page_texts if text.strip()).strip()
        finally:
            document.close()

    def _extract_image_text(self, image: Image.Image) -> str:
        self._ensure_tesseract_available()
        rgb_image = image.convert("RGB")
        return pytesseract.image_to_string(rgb_image, lang=self.settings.ocr_languages).strip()

    def _ensure_tesseract_available(self) -> None:
        configured = self.settings.tesseract_cmd
        resolved = configured or shutil.which("tesseract")
        if not resolved:
            raise AppError(
                "OCR runtime is not configured. Install Tesseract or set TESSERACT_CMD.",
                code="ocr_runtime_unavailable",
                status_code=503,
            )
        pytesseract.pytesseract.tesseract_cmd = resolved
