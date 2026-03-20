import re

from paddleocr import PaddleOCR

from app.schemas.ocr import OCRField, OCRResult

_ocr = PaddleOCR(use_textline_orientation=True, lang="korean")

ID_NUMBER_PATTERN = re.compile(r"\d{6}-\d{7}")
ACCOUNT_NUMBER_PATTERN = re.compile(r"\d{2,4}[-]\d{2,4}[-]\d{2,4}([-]\d{2,4})?")
BANK_NAMES = ["농협", "NH", "우리", "국민", "신한", "하나", "기업", "SC", "카카오", "토스", "케이"]
NAME_LABEL_KEYWORDS = ["예금주", "성명", "고객명", "받는분", "입금주"]
KOREAN_NAME_PATTERN = re.compile(r"^[가-힣]{2,4}$")
DATE_PATTERN = re.compile(r"\d{4}[.\-/]")
NON_NAME_KEYWORDS = ["은행", "Bank", "통장", "예금", "계좌", "지점", "안내", "발행", "관리", "인터넷", "전자"]


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

        # 통장사본 키워드는 스킵 (Gate 2 키워드 매칭에서 처리)
        if any(kw in text for kw in ["통장사본", "통장"]):
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
                acct_match = ACCOUNT_NUMBER_PATTERN.search(text)
                if acct_match:
                    fields.append(OCRField(field_name="account_number", value=acct_match.group(), confidence=score))
                    has_account = True
                    continue
                if i + 1 < len(texts):
                    next_text = texts[i + 1].strip()
                    next_score = scores[i + 1]
                    next_match = ACCOUNT_NUMBER_PATTERN.search(next_text)
                    if next_match:
                        fields.append(OCRField(field_name="account_number", value=next_match.group(), confidence=next_score))
                        has_account = True
                continue

    # name: 후보 추출 + 점수화
    name_field = _score_name_candidates(texts, scores, raw_lines)
    if name_field:
        fields.append(name_field)

    return OCRResult(fields=fields, raw_text="\n".join(raw_lines) if raw_lines else None)


def _score_name_candidates(
    texts: list[str], scores: list[float], raw_lines: list[str]
) -> OCRField | None:
    """후보 추출 + 점수화로 이름 필드를 결정한다."""
    candidates: list[tuple[str, float, float]] = []  # (name, ocr_confidence, score)

    for i, (text, conf) in enumerate(zip(texts, scores)):
        text = text.strip()
        if not text or conf < 0.5:
            continue

        score = 0.0
        name_value = text

        # 이미 다른 필드로 쓰인 패턴이면 스킵
        if ACCOUNT_NUMBER_PATTERN.search(text):
            continue
        if DATE_PATTERN.search(text):
            continue
        if any(kw in text for kw in NON_NAME_KEYWORDS):
            continue

        # 강한 신호: 앞 줄이 라벨 키워드 (짧은 라벨만)
        if i > 0:
            prev = texts[i - 1].strip()
            if len(prev) <= 10 and any(kw in prev for kw in NAME_LABEL_KEYWORDS):
                score += 5.0

        # 강한 신호: "님" 포함
        if "님" in text:
            score += 4.0
            name_value = text.replace("님", "").strip()
            if not name_value:
                # 단독 "님"이면 앞 줄이 이름
                if i > 0:
                    prev = texts[i - 1].strip()
                    if KOREAN_NAME_PATTERN.match(prev):
                        name_value = prev
                        score += 3.0
                    else:
                        continue
                else:
                    continue

        # 중간 신호: 한글 2~4자 단독 토큰
        if KOREAN_NAME_PATTERN.match(name_value):
            score += 3.0

        # 중간 신호: 문서 상단 (앞쪽 30% 이내)
        position_ratio = i / max(len(texts), 1)
        if position_ratio < 0.3:
            score += 1.0

        # 약한 신호: OCR confidence
        score += conf * 1.0

        # 최소 점수 기준
        if score >= 3.0 and name_value:
            candidates.append((name_value, conf, score))

    if not candidates:
        return None

    # 최고 점수 후보 선택
    best = max(candidates, key=lambda x: x[2])
    return OCRField(field_name="name", value=best[0], confidence=best[1])
