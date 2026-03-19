import re

from paddleocr import PaddleOCR

from app.schemas.ocr import OCRField, OCRResult

_ocr = PaddleOCR(use_textline_orientation=True, lang="korean")

ID_NUMBER_PATTERN = re.compile(r"\d{6}-\d{7}")
ACCOUNT_NUMBER_PATTERN = re.compile(r"\d{2,4}[-]\d{2,4}[-]\d{2,4}([-]\d{2,4})?")
BANK_NAMES = ["농협", "NH", "우리", "국민", "신한", "하나", "기업", "SC", "카카오", "토스", "케이"]


def _run_ocr(image_path: str) -> tuple[list[str], list[float]]:
    """PaddleOCR 실행 후 (texts, scores) 반환."""
    results = list(_ocr.predict(image_path))
    texts: list[str] = []
    scores: list[float] = []
    for res in results:
        if "rec_texts" in res:
            texts.extend(res["rec_texts"])
            scores.extend(res["rec_scores"])
    return texts, scores


def extract_id_card(image_path: str) -> OCRResult:
    texts, scores = _run_ocr(image_path)

    fields: list[OCRField] = []
    raw_lines: list[str] = []
    has_doc_title = False
    has_name = False

    for text, score in zip(texts, scores):
        text = text.strip()
        if not text:
            continue
        raw_lines.append(text)

        if "주민등록증" in text:
            fields.append(OCRField(field_name="doc_title", value=text, confidence=score))
            has_doc_title = True
            continue

        id_match = ID_NUMBER_PATTERN.search(text)
        if id_match:
            fields.append(OCRField(field_name="id_number", value=id_match.group(), confidence=score))
            continue

        if has_doc_title and not has_name and score >= 0.8:
            fields.append(OCRField(field_name="name", value=text, confidence=score))
            has_name = True
            continue

    return OCRResult(fields=fields, raw_text="\n".join(raw_lines) if raw_lines else None)


def extract_bank_account(image_path: str) -> OCRResult:
    texts, scores = _run_ocr(image_path)

    fields: list[OCRField] = []
    raw_lines: list[str] = []
    has_account = False
    has_name = False
    has_bank = False

    for i, (text, score) in enumerate(zip(texts, scores)):
        text = text.strip()
        if not text:
            continue
        raw_lines.append(text)

        # doc_title: 통장사본 키워드
        if any(kw in text for kw in ["통장사본", "통장"]) and not any(
            f.field_name == "doc_title" for f in fields
        ):
            fields.append(OCRField(field_name="doc_title", value=text, confidence=score))
            continue

        # bank_name: 은행명 인식 (짧은 텍스트만, 문장 제외)
        if not has_bank and score >= 0.7 and len(text) <= 15:
            if any(bank in text for bank in BANK_NAMES) and ("은행" in text or "Bank" in text.title()):
                fields.append(OCRField(field_name="bank_name", value=text, confidence=score))
                has_bank = True
                continue

        # account_number: "계좌번호" 라벨과 같은 줄 또는 다음 줄
        if not has_account:
            if "계좌번호" in text or "계좌 번 호" in text:
                # 같은 줄에 번호가 있는 경우
                acct_match = ACCOUNT_NUMBER_PATTERN.search(text)
                if acct_match:
                    fields.append(OCRField(field_name="account_number", value=acct_match.group(), confidence=score))
                    has_account = True
                    continue
                # 다음 줄에서 찾기
                if i + 1 < len(texts):
                    next_text = texts[i + 1].strip()
                    next_score = scores[i + 1]
                    next_match = ACCOUNT_NUMBER_PATTERN.search(next_text)
                    if next_match:
                        fields.append(OCRField(field_name="account_number", value=next_match.group(), confidence=next_score))
                        has_account = True
                continue

        # name: "님" 포함 or 단독 "님"일 때 앞 줄 참조
        if not has_name and score >= 0.8:
            if text == "님" and len(raw_lines) >= 2:
                # "님"이 단독 줄이면 바로 앞 텍스트가 이름
                prev_text = raw_lines[-2]
                if len(prev_text) <= 10:
                    fields.append(OCRField(field_name="name", value=prev_text, confidence=score))
                    has_name = True
                    continue
            elif "님" in text and len(text.replace("님", "").strip()) <= 10:
                name_value = text.replace("님", "").strip()
                if name_value:
                    fields.append(OCRField(field_name="name", value=name_value, confidence=score))
                    has_name = True
                    continue

    return OCRResult(fields=fields, raw_text="\n".join(raw_lines) if raw_lines else None)
