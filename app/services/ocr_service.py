import os
import re
import threading

import numpy as np

os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

from paddleocr import PaddleOCR
from paddlex.inference.models.text_recognition.processors import CTCLabelDecode

from app.schemas.ocr import CharConfidence, OCRField, OCRResult

# --- Monkey-patch: 글자별 confidence 추출 ---
_orig_ctc_call = CTCLabelDecode.__call__


def _patched_ctc_call(self, pred, return_word_box=False, **kwargs):
    preds = np.array(pred[0])
    preds_idx = preds.argmax(axis=-1)
    preds_prob = preds.max(axis=-1)
    ignored_tokens = self.get_ignored_tokens()
    if not hasattr(self, "_all_char_confs"):
        self._all_char_confs = []
    for batch_idx in range(len(preds_idx)):
        selection = np.ones(len(preds_idx[batch_idx]), dtype=bool)
        selection[1:] = preds_idx[batch_idx][1:] != preds_idx[batch_idx][:-1]
        for tok in ignored_tokens:
            selection &= preds_idx[batch_idx] != tok
        chars = [self.character[i] for i in preds_idx[batch_idx][selection]]
        confs = preds_prob[batch_idx][selection].tolist()
        self._all_char_confs.append(list(zip(chars, confs)))
    return _orig_ctc_call(self, pred, return_word_box=return_word_box, **kwargs)


CTCLabelDecode.__call__ = _patched_ctc_call
# --- End monkey-patch ---

_ocr_lock = threading.Lock()

ID_NUMBER_PATTERN = re.compile(r"\d{6}-\d{7}")
ACCOUNT_NUMBER_PATTERN = re.compile(r"\d{2,4}[-]\d{2,4}[-]\d{2,4}([-]\d{2,4})?")
BANK_NAMES = ["농협", "NH", "우리", "국민", "신한", "하나", "기업", "SC", "카카오", "토스", "케이"]
NAME_LABEL_KEYWORDS = ["예금주", "성명", "고객명", "받는분", "입금주"]
KOREAN_NAME_PATTERN = re.compile(r"^[가-힣]{2,4}$")
DATE_PATTERN = re.compile(r"\d{4}[.\-/]")
NON_NAME_KEYWORDS = ["은행", "Bank", "통장", "예금", "계좌", "지점", "안내", "발행", "관리", "인터넷", "전자"]

# 신분증 주소 추출용
ADDRESS_KEYWORDS = ["시", "구", "동", "로", "길", "읍", "면", "리", "번지", "아파트", "호"]
ISSUER_KEYWORDS = ["청장", "장관", "시장", "군수", "발급"]
# 신분증 발급일 추출용 (YYYY.MM.DD / YYYY. MM. DD / YYYY-MM-DD 등)
ISSUE_DATE_PATTERN = re.compile(r"(\d{4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})")


def _run_ocr(image_path: str) -> tuple[list[str], list[float], dict[str, list[tuple[str, float]]]]:
    """PaddleOCR 실행 후 (texts, scores, char_confs_map) 반환."""
    with _ocr_lock:
        ocr = PaddleOCR(use_textline_orientation=True, lang="korean")
        post = ocr.paddlex_pipeline.text_rec_model.post_op
        post._all_char_confs = []
        results = list(ocr.predict(image_path))

    # 글자별 confidence를 text 기준으로 매핑
    char_confs_map: dict[str, list[tuple[str, float]]] = {}
    for cc in post._all_char_confs:
        text = "".join(c for c, _ in cc)
        char_confs_map[text] = cc

    texts: list[str] = []
    scores: list[float] = []
    for res in results:
        if "rec_texts" in res:
            texts.extend(res["rec_texts"])
            scores.extend(res["rec_scores"])
    return texts, scores, char_confs_map


def _get_char_confs(text: str, char_confs_map: dict, value: str | None = None) -> list[CharConfidence]:
    """텍스트에 해당하는 글자별 confidence를 CharConfidence 리스트로 반환.
    value가 지정되면 해당 value에 매칭되는 부분만 추출."""
    cc = char_confs_map.get(text, [])
    if not cc:
        return []
    if value and value != text:
        # value가 원본 text의 부분인 경우, 해당 위치의 char_confs만 추출
        full_text = "".join(ch for ch, _ in cc)
        start = full_text.find(value)
        if start >= 0:
            cc = cc[start:start + len(value)]
    return [CharConfidence(char=ch, confidence=conf) for ch, conf in cc]


def extract_id_card(image_path: str) -> OCRResult:
    texts, scores, char_confs_map = _run_ocr(image_path)

    fields: list[OCRField] = []
    raw_lines: list[str] = []
    has_doc_title = False
    has_name = False
    has_id_number = False
    address_parts: list[tuple[str, float]] = []
    issue_date_field: OCRField | None = None

    for text, score in zip(texts, scores):
        text = text.strip()
        if not text:
            continue
        raw_lines.append(text)

        if "주민등록증" in text:
            has_doc_title = True
            continue

        id_match = ID_NUMBER_PATTERN.search(text)
        if id_match and not has_id_number:
            fields.append(OCRField(field_name="id_number", value=id_match.group(), confidence=score,
                                   char_confidences=_get_char_confs(text, char_confs_map, id_match.group())))
            has_id_number = True
            continue

        if has_doc_title and not has_name and score >= 0.8:
            fields.append(OCRField(field_name="name", value=text.replace(" ", ""), confidence=score,
                                   char_confidences=_get_char_confs(text, char_confs_map, text.replace(" ", ""))))
            has_name = True
            continue

        # 주소: 주소 키워드가 포함된 줄 수집 (발급 주체 제외)
        if any(kw in text for kw in ISSUER_KEYWORDS):
            pass  # "~청장", "발급" 등은 주소가 아님
        else:
            addr_keyword_count = sum(1 for kw in ADDRESS_KEYWORDS if kw in text)
            if addr_keyword_count >= 2 or (addr_keyword_count >= 1 and len(text) >= 8):
                address_parts.append((text, score))
                continue

        # 발급일: 날짜 패턴 + "발급" 키워드 근처
        if not issue_date_field:
            date_match = ISSUE_DATE_PATTERN.search(text)
            if date_match:
                date_str = f"{date_match.group(1)}.{date_match.group(2).zfill(2)}.{date_match.group(3).zfill(2)}"
                issue_date_field = OCRField(field_name="issue_date", value=date_str, confidence=score,
                                              char_confidences=_get_char_confs(text, char_confs_map))

    # 주소 조합
    if address_parts:
        combined_addr = " ".join(part for part, _ in address_parts)
        avg_conf = sum(conf for _, conf in address_parts) / len(address_parts)
        combined_char_confs: list[CharConfidence] = []
        for part, _ in address_parts:
            combined_char_confs.extend(_get_char_confs(part, char_confs_map))
        fields.append(OCRField(field_name="address", value=combined_addr, confidence=avg_conf,
                               char_confidences=combined_char_confs))

    if issue_date_field:
        fields.append(issue_date_field)

    return OCRResult(fields=fields, raw_text="\n".join(raw_lines) if raw_lines else None)


def extract_bank_account(image_path: str) -> OCRResult:
    texts, scores, char_confs_map = _run_ocr(image_path)

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
                fields.append(OCRField(field_name="bank_name", value=text, confidence=score,
                                       char_confidences=_get_char_confs(text, char_confs_map)))
                has_bank = True
                continue

        # account_number: "계좌번호" 라벨과 같은 줄 또는 다음 줄
        if not has_account:
            if "계좌번호" in text or "계좌 번 호" in text:
                acct_match = ACCOUNT_NUMBER_PATTERN.search(text)
                if acct_match:
                    fields.append(OCRField(field_name="account_number", value=acct_match.group(), confidence=score,
                                           char_confidences=_get_char_confs(text, char_confs_map, acct_match.group())))
                    has_account = True
                    continue
                if i + 1 < len(texts):
                    next_text = texts[i + 1].strip()
                    next_score = scores[i + 1]
                    next_match = ACCOUNT_NUMBER_PATTERN.search(next_text)
                    if next_match:
                        fields.append(OCRField(field_name="account_number", value=next_match.group(), confidence=next_score,
                                               char_confidences=_get_char_confs(next_text, char_confs_map)))
                        has_account = True
                continue

    # name: "님" 패턴 우선 탐색 → 없으면 후보 점수화
    name_field = _extract_name_by_nim(texts, scores, char_confs_map)
    if not name_field:
        name_field = _score_name_candidates(texts, scores, raw_lines, char_confs_map)
    if name_field:
        fields.append(name_field)

    return OCRResult(fields=fields, raw_text="\n".join(raw_lines) if raw_lines else None)


def _extract_name_by_nim(
    texts: list[str], scores: list[float], char_confs_map: dict | None = None,
) -> OCRField | None:
    """통장사본에서 '님' 패턴으로 이름을 추출한다.

    패턴:
    1. "홍길동 님" 또는 "홍길동님" → 같은 줄에서 추출
    2. "홍길동" + 다음 줄 "님" → 앞 줄이 이름
    """
    for i, (text, conf) in enumerate(zip(texts, scores)):
        text = text.strip()
        if not text:
            continue

        # 패턴 1: 같은 줄에 "님" 포함 (예: "홍길동 님", "홍길동님")
        if "님" in text:
            name = text.replace("님", "").strip().replace(" ", "")
            if name and KOREAN_NAME_PATTERN.match(name):
                return OCRField(
                    field_name="name", value=name, confidence=conf,
                    char_confidences=_get_char_confs(text, char_confs_map or {}, name),
                )

        # 패턴 2: 이 줄이 한글 이름이고 다음 줄이 "님"
        if i + 1 < len(texts):
            next_text = texts[i + 1].strip()
            if next_text == "님" and KOREAN_NAME_PATTERN.match(text.replace(" ", "")):
                name = text.replace(" ", "")
                return OCRField(
                    field_name="name", value=name, confidence=conf,
                    char_confidences=_get_char_confs(text, char_confs_map or {}, name),
                )

    return None


def _score_name_candidates(
    texts: list[str], scores: list[float], raw_lines: list[str],
    char_confs_map: dict | None = None,
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
    name_val = best[0].replace(" ", "")
    cc = _get_char_confs(best[0], char_confs_map or {}, name_val)
    return OCRField(field_name="name", value=name_val, confidence=best[1], char_confidences=cc)
