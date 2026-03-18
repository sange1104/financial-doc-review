import re
from paddleocr import PaddleOCR

from app.schemas.ocr import OCRField, OCRResult

_ocr = PaddleOCR(use_textline_orientation=True, lang="korean")

ID_NUMBER_PATTERN = re.compile(r"\d{6}-\d{7}")


def extract_ocr(image_path: str) -> OCRResult:
    results = list(_ocr.predict(image_path))

    texts: list[str] = []
    scores: list[float] = []

    for res in results:
        if "rec_texts" in res:
            texts.extend(res["rec_texts"])
            scores.extend(res["rec_scores"])

    fields: list[OCRField] = []
    raw_lines: list[str] = []

    has_doc_title = False
    has_name = False

    for text, score in zip(texts, scores):
        text = text.strip()
        if not text:
            continue

        raw_lines.append(text)

        id_match = ID_NUMBER_PATTERN.search(text)

        if "주민등록증" in text:
            fields.append(
                OCRField(field_name="doc_title", value=text, confidence=score)
            )
            has_doc_title = True
            continue

        if id_match:
            fields.append(
                OCRField(
                    field_name="id_number",
                    value=id_match.group(),
                    confidence=score,
                )
            )
            continue

        if has_doc_title and not has_name and score >= 0.8:
            # MVP heuristic:
            # first high-confidence non-title, non-id text after doc title
            fields.append(
                OCRField(field_name="name", value=text, confidence=score)
            )
            has_name = True
            continue

    return OCRResult(
        fields=fields,
        raw_text="\n".join(raw_lines) if raw_lines else None,
    )