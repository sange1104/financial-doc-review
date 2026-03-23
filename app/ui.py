import json

import requests
import streamlit as st

API_BASE = "http://localhost:8001/api/review"

FIELD_LABELS = {
    "name": "👤 이름",
    "id_number": "🔢 주민등록번호",
    "address": "🏠 주소",
    "issue_date": "📅 발급일",
    "account_number": "💳 계좌번호",
    "bank_name": "🏦 은행명",
}

DECISION_CONFIG = {
    "pass": {
        "icon": "✅",
        "label": "PASS",
        "bg": "linear-gradient(135deg, #00c853, #69f0ae)",
        "msg": "문서가 정상적으로 확인되었습니다.",
    },
    "retake": {
        "icon": "📸",
        "label": "RETAKE",
        "bg": "linear-gradient(135deg, #ff1744, #ff8a80)",
        "msg": "이미지를 다시 촬영해주세요.",
    },
    "review": {
        "icon": "🔍",
        "label": "REVIEW",
        "bg": "linear-gradient(135deg, #ff9100, #ffd180)",
        "msg": "담당자 확인이 필요합니다.",
    },
    "invalid_doc_type": {
        "icon": "⚠️",
        "label": "INVALID DOCUMENT",
        "bg": "linear-gradient(135deg, #6a1b9a, #ce93d8)",
        "msg": "올바른 문서 유형을 업로드해주세요.",
    },
}

# retake 사유 한글 번역 + 행동 가이드
RETAKE_REASONS = {
    "image too blurry": {
        "label": "📷 이미지가 흐릿합니다",
        "guide": "카메라 초점을 맞추고 흔들리지 않게 촬영해주세요.",
    },
    "glare": {
        "label": "💡 빛반사(글레어)가 감지되었습니다",
        "guide": "조명을 조절하거나 각도를 바꿔서 빛반사를 피해주세요.",
    },
    "image resolution too low": {
        "label": "📐 이미지 해상도가 너무 낮습니다",
        "guide": "더 가까이에서 촬영하거나 고해상도 설정으로 촬영해주세요.",
    },
    "too small": {
        "label": "🔎 이미지가 너무 작습니다",
        "guide": "문서가 화면에 크게 나오도록 가까이에서 촬영해주세요.",
    },
    "nearly all black": {
        "label": "⬛ 이미지가 거의 검은색입니다",
        "guide": "밝은 환경에서 문서를 다시 촬영해주세요.",
    },
    "nearly all white": {
        "label": "⬜ 이미지가 거의 흰색입니다",
        "guide": "문서가 카메라 프레임 안에 있는지 확인해주세요.",
    },
    "could not be read": {
        "label": "❌ 이미지 파일을 읽을 수 없습니다",
        "guide": "다른 이미지 파일로 다시 시도해주세요.",
    },
    "too little text": {
        "label": "📝 문서에서 텍스트를 거의 인식하지 못했습니다",
        "guide": "문서 전체가 보이도록 촬영하고, 글자가 선명한지 확인해주세요.",
    },
    "No required fields": {
        "label": "🚫 필수 정보를 찾을 수 없습니다",
        "guide": "문서의 핵심 정보(이름, 번호 등)가 모두 보이도록 촬영해주세요.",
    },
    "Glare obscured": {
        "label": "💡 빛반사로 인해 문서 내용을 읽을 수 없습니다",
        "guide": "조명을 조절하고 빛반사가 없는 상태에서 다시 촬영해주세요.",
    },
    "VLM could not determine document type": {
        "label": "❓ 문서 유형을 판별할 수 없습니다",
        "guide": "문서 전체가 보이도록 다시 촬영해주세요.",
    },
}


REVIEW_REASONS = {
    "name field not found": "👤 이름을 찾을 수 없습니다",
    "name confidence too low": "👤 이름 인식 신뢰도가 낮습니다",
    "id_number field not found": "🔢 주민등록번호를 찾을 수 없습니다",
    "id_number format invalid": "🔢 주민등록번호 형식이 올바르지 않습니다",
    "id_number confidence too low": "🔢 주민등록번호 인식 신뢰도가 낮습니다",
    "account_number field not found": "💳 계좌번호를 찾을 수 없습니다",
    "account_number confidence too low": "💳 계좌번호 인식 신뢰도가 낮습니다",
    "bank_name field not found": "🏦 은행명을 찾을 수 없습니다",
    "bank_name confidence too low": "🏦 은행명 인식 신뢰도가 낮습니다",
    "glare detected on document": "💡 문서에서 빛반사가 감지되었습니다",
    "image too blurry": "📷 이미지가 흐릿합니다",
    "image resolution too low": "📐 이미지 해상도가 낮습니다",
    "VLM could not determine document type": "❓ 문서 유형을 판별할 수 없습니다",
    "VLM detected bank account": "⚠️ VLM이 통장사본으로 판별했습니다",
    "VLM detected ID card": "⚠️ VLM이 신분증으로 판별했습니다",
    "address confidence too low": "🏠 주소 인식 신뢰도가 낮습니다",
    "issue_date confidence too low": "📅 발급일 인식 신뢰도가 낮습니다",
    "id_number low confidence chars": "🔢 주민등록번호 일부 글자 인식 신뢰도가 낮습니다",
    "account_number low confidence chars": "💳 계좌번호 일부 글자 인식 신뢰도가 낮습니다",
    "name low confidence chars": "👤 이름 일부 글자 인식 신뢰도가 낮습니다",
    "bank_name low confidence chars": "🏦 은행명 일부 글자 인식 신뢰도가 낮습니다",
    "address low confidence chars": "🏠 주소 일부 글자 인식 신뢰도가 낮습니다",
    "issue_date low confidence chars": "📅 발급일 일부 글자 인식 신뢰도가 낮습니다",
}


def _get_retake_info(reason: str) -> tuple[str, str]:
    """retake 사유 영문 → 한글 라벨 + 행동 가이드 반환."""
    for key, info in RETAKE_REASONS.items():
        if key.lower() in reason.lower():
            return info["label"], info["guide"]
    return "📸 이미지를 다시 촬영해주세요", "문서가 선명하고 전체가 보이도록 촬영해주세요."


def _get_review_reasons_kr(reason: str) -> list[str]:
    """review 사유 영문 → 한글 리스트 반환."""
    parts = [r.strip() for r in reason.split(";")]
    # 긴 키부터 매칭하여 부분 문자열 오매칭 방지 (e.g. "name" vs "bank_name")
    sorted_keys = sorted(REVIEW_REASONS.keys(), key=len, reverse=True)
    result = []
    for part in parts:
        matched = False
        for key in sorted_keys:
            if key.lower() in part.lower():
                result.append(REVIEW_REASONS[key])
                matched = True
                break
        if not matched:
            result.append(part)
    return result


st.set_page_config(page_title="Document Review", layout="centered", page_icon="🔍")

# 다크모드 감지
is_dark = st.get_option("theme.base") == "dark"

# 글로벌 스타일
st.markdown("""
<style>
    .decision-banner {
        padding: 30px;
        border-radius: 16px;
        text-align: center;
        margin: 20px 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .decision-banner h1 {
        color: white;
        font-size: 2.8em;
        margin: 0;
        text-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    .decision-banner p {
        color: rgba(255,255,255,0.9);
        font-size: 1.1em;
        margin: 8px 0 0 0;
    }
    .reason-box {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 15px 20px;
        margin: 10px 0 20px 0;
        border-left: 4px solid #5c6bc0;
    }
    .retake-guide {
        background: #fff3e0;
        border-radius: 12px;
        padding: 18px 22px;
        margin: 10px 0 20px 0;
        border-left: 4px solid #ff9100;
    }
    .retake-guide .retake-label {
        font-weight: 700;
        font-size: 1.05em;
        margin-bottom: 6px;
    }
    .retake-guide .retake-action {
        color: #555;
        font-size: 0.95em;
    }
    .field-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 14px 18px;
        margin: 8px 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        transition: transform 0.2s;
    }
    .field-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }
    .field-label {
        color: #888;
        font-size: 0.85em;
        margin-bottom: 4px;
    }
    .field-value {
        font-size: 1.15em;
        font-weight: 600;
        color: #1a1a1a;
    }
    .conf-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.8em;
        font-weight: 600;
        float: right;
        margin-top: 2px;
    }
    .conf-high { background: #e8f5e9; color: #2e7d32; }
    .conf-mid { background: #fff3e0; color: #e65100; }
    .conf-low { background: #ffebee; color: #c62828; }
    .quality-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    .quality-card .value {
        font-size: 1.8em;
        font-weight: 700;
    }
    .quality-card .label {
        color: #888;
        font-size: 0.9em;
        margin-top: 4px;
    }
    .section-header {
        font-size: 1.2em;
        font-weight: 600;
        color: #333;
        margin: 25px 0 15px 0;
        padding-bottom: 8px;
        border-bottom: 2px solid #e8eaf6;
    }
    .status-good { color: #2e7d32; }
    .status-bad { color: #c62828; }
</style>
""", unsafe_allow_html=True)

# 헤더
st.markdown(f"""
<div style="text-align: center; padding: 30px 0 10px 0;">
    <div style="font-size: 2.8em; font-weight: 800; letter-spacing: -1px; color: {'#e8eaff' if is_dark else '#1a237e'};">🔍 Document Review</div>
    <div style="display: inline-block; margin-top: 8px; padding: 6px 24px; border-radius: 20px; font-weight: 600; font-size: 0.95em; background: {'#3d37a1' if is_dark else '#e8eaf6'}; color: {'#e8d5ff' if is_dark else '#4a148c'};">신분증 및 통장사본 자동 검증 시스템</div>
</div>
""", unsafe_allow_html=True)

st.divider()

# 문서 유형 선택
col_type, col_upload = st.columns([1, 2])
with col_type:
    doc_type = st.radio("📋 문서 유형", ["신분증", "통장사본"], horizontal=True)
with col_upload:
    uploaded = st.file_uploader("이미지를 드래그하거나 클릭하여 업로드", type=["png", "jpg", "jpeg"], label_visibility="visible")

if not uploaded:
    st.markdown("""
    <div style='text-align: center; padding: 60px 20px; color: #aaa;'>
        <p style='font-size: 3em; margin-bottom: 10px;'>📤</p>
        <p style='font-size: 1.2em;'>문서 이미지를 업로드하면 자동으로 분석이 시작됩니다</p>
        <p style='font-size: 0.9em;'>지원 형식: PNG, JPG, JPEG</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

st.divider()

endpoint = f"{API_BASE}/id-card/stream" if doc_type == "신분증" else f"{API_BASE}/bank-account/stream"

# 분석 결과 캐시: 같은 파일+문서유형이면 재분석하지 않음
cache_key = f"{uploaded.name}_{uploaded.size}_{doc_type}"
if st.session_state.get("_cache_key") != cache_key:
    st.session_state._cache_key = cache_key
    st.session_state._cached_data = None
    st.session_state.review_confirmed = False
    st.session_state.edited_fields = {}

if st.session_state._cached_data is None:
    data = None
    with st.status("🔄 문서를 분석하고 있습니다...", expanded=True) as status:
        step_text = st.empty()
        resp = requests.post(
            endpoint,
            files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type)},
            stream=True,
        )
        if resp.status_code != 200:
            st.error(f"API 오류: {resp.status_code} - {resp.text}")
            st.stop()

        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            if event["type"] == "progress":
                step_text.markdown(event["message"])
            elif event["type"] == "result":
                data = event["data"]
            elif event["type"] == "error":
                st.error(f"처리 오류: {event['message']}")
                st.stop()

        step_text.empty()
        status.update(label="✅ 분석 완료!", state="complete")

    if data is None:
        st.error("응답을 받지 못했습니다.")
        st.stop()
    st.session_state._cached_data = data
else:
    data = st.session_state._cached_data
decision = data["decision"]
cfg = DECISION_CONFIG[decision]

# 판정 결과 배너
st.markdown(f"""
<div class="decision-banner" style="background: {cfg['bg']};">
    <h1>{cfg['icon']} {cfg['label']}</h1>
    <p>{cfg['msg']}</p>
</div>
""", unsafe_allow_html=True)

# retake인 경우: 한글 사유 + 행동 가이드
if decision == "retake":
    retake_label, retake_guide = _get_retake_info(data["reason"])
    st.markdown(f"""
    <div class="retake-guide">
        <div class="retake-label">{retake_label}</div>
        <div class="retake-action">👉 {retake_guide}</div>
    </div>
    """, unsafe_allow_html=True)
elif decision == "invalid_doc_type":
    detected = data.get("document_type", "")
    reason = data.get("reason", "")
    if detected == "id_card":
        inv_label = "⚠️ 신분증이 감지되었습니다. 통장사본을 업로드해주세요."
    elif detected == "bank_account_doc":
        inv_label = "⚠️ 통장사본이 감지되었습니다. 신분증을 업로드해주세요."
    elif reason:
        inv_label = f"⚠️ {reason}"
    else:
        inv_label = "⚠️ 선택한 문서 유형과 다른 문서가 감지되었습니다."
    st.markdown(f"""
    <div class="retake-guide" style="border-left-color: #6a1b9a; background: #f3e5f5;">
        <div class="retake-label">{inv_label}</div>
        <div class="retake-action">👉 올바른 문서를 선택하거나, 정확한 문서를 업로드해주세요.</div>
    </div>
    """, unsafe_allow_html=True)
elif decision == "review":
    reasons_kr = _get_review_reasons_kr(data["reason"])
    reasons_html = "".join(f"<li>{r}</li>" for r in reasons_kr)
    st.markdown(f"""
    <div class="reason-box">
        <span style="font-weight: 600;">🔍 확인이 필요한 항목:</span>
        <ul style="margin: 8px 0 0 0; padding-left: 20px;">{reasons_html}</ul>
    </div>
    """, unsafe_allow_html=True)
elif decision != "pass":
    st.markdown(f"""
    <div class="reason-box">
        <span style="font-weight: 600;">💬 판정 사유:</span> {data['reason']}
    </div>
    """, unsafe_allow_html=True)

# 이미지 + OCR 결과
col_img, col_ocr = st.columns([1, 1], gap="large")

with col_img:
    st.markdown(f'<div class="section-header">🖼️ 업로드된 {doc_type}</div>', unsafe_allow_html=True)
    st.image(uploaded, use_container_width=True)

def _render_char_confs_hint(char_confs: list[dict]) -> str:
    """글자별 confidence를 색상 코딩된 HTML로 렌더링."""
    if not char_confs:
        return ""
    chars_html = ""
    for cc in char_confs:
        c, c_conf = cc["char"], cc["confidence"]
        if c_conf >= 0.9:
            color = "#2e7d32"
        elif c_conf >= 0.7:
            color = "#e65100"
        elif c_conf >= 0.5:
            color = "#c62828"
        else:
            color = "#ffffff"
            chars_html += f'<span title="{c_conf:.0%}" style="background:#c62828;color:#fff;padding:0 2px;border-radius:3px;font-weight:700;">{c}</span>'
            continue
        chars_html += f'<span title="{c_conf:.0%}" style="color:{color};">{c}</span>'
    return chars_html


def _get_low_conf_hint(char_confs: list[dict], threshold: float = 0.7) -> str:
    """confidence가 낮은 글자들의 위치를 안내 텍스트로 반환."""
    low = [(i + 1, cc["char"], cc["confidence"]) for i, cc in enumerate(char_confs) if cc["confidence"] < threshold]
    if not low:
        return ""
    parts = [f"**{pos}번째 '{ch}'** ({conf:.0%})" for pos, ch, conf in low]
    return f"확인 필요: {', '.join(parts)}"


is_review = decision == "review"

# 확인 완료 상태 관리
if "review_confirmed" not in st.session_state:
    st.session_state.review_confirmed = False
if "edited_fields" not in st.session_state:
    st.session_state.edited_fields = {}

editing = is_review and not st.session_state.review_confirmed

with col_ocr:
    if editing:
        header_text = "✏️ 정보 확인 및 수정"
    elif is_review and st.session_state.review_confirmed:
        header_text = "✅ 확인 완료된 정보"
    else:
        header_text = "📝 추출된 정보"
    st.markdown(f'<div class="section-header">{header_text}</div>', unsafe_allow_html=True)

    if not data["ocr"]["fields"]:
        st.markdown("""
        <div style='text-align: center; padding: 40px; color: #aaa;'>
            <p style='font-size: 2em;'>🚫</p>
            <p>추출된 필드가 없습니다</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        fields = data["ocr"]["fields"]
        if is_review:
            fields = sorted(fields, key=lambda f: f["confidence"])

        for field in fields:
            fname = field["field_name"]
            label = FIELD_LABELS.get(fname, fname)
            conf = field["confidence"]
            char_confs = field.get("char_confidences", [])

            if conf >= 0.9:
                conf_class = "conf-high"
            elif conf >= 0.7:
                conf_class = "conf-mid"
            else:
                conf_class = "conf-low"

            if editing:
                # 편집 모드: 색상 힌트 + 입력 필드
                chars_hint = _render_char_confs_hint(char_confs)
                if chars_hint:
                    st.markdown(f"""
                    <div style="margin-bottom: -10px;">
                        <span style="font-size: 0.8em; color: #888;">{label}</span>
                        <span class="conf-badge {conf_class}" style="font-size: 0.75em;">{conf:.0%}</span>
                    </div>
                    <div style="font-size: 1.1em; margin-bottom: 2px; font-family: monospace;">{chars_hint}</div>
                    """, unsafe_allow_html=True)

                low_hint = _get_low_conf_hint(char_confs)
                edited = st.text_input(
                    label if not chars_hint else "수정값",
                    value=field["value"] or "",
                    key=f"edit_{fname}",
                    label_visibility="collapsed" if chars_hint else "visible",
                )
                if low_hint:
                    st.caption(low_hint)
                st.session_state.edited_fields[fname] = edited

            elif is_review and st.session_state.review_confirmed:
                # 확인 완료 모드: 수정된 값을 읽기 전용으로 표시
                confirmed_value = st.session_state.edited_fields.get(fname, field["value"])
                changed = confirmed_value != field["value"]
                badge = ' <span style="background:#1565c0;color:#fff;padding:1px 8px;border-radius:10px;font-size:0.75em;">수정됨</span>' if changed else ""
                st.markdown(f"""
                <div class="field-card">
                    <div class="field-label">{label}{badge}</div>
                    <span class="field-value">{confirmed_value}</span>
                    <span class="conf-badge {conf_class}">{conf:.0%}</span>
                </div>
                """, unsafe_allow_html=True)

            else:
                # 읽기 전용 모드 (pass, retake 등)
                chars_html = _render_char_confs_hint(char_confs)
                value_html = f'<span class="field-value">{chars_html}</span>' if chars_html else f'<span class="field-value">{field["value"]}</span>'
                st.markdown(f"""
                <div class="field-card">
                    <div class="field-label">{label}</div>
                    {value_html}
                    <span class="conf-badge {conf_class}">{conf:.0%}</span>
                </div>
                """, unsafe_allow_html=True)

        if is_review:
            st.divider()
            if editing:
                if st.button("✅ 확인 완료", type="primary", use_container_width=True):
                    st.session_state.review_confirmed = True
                    st.rerun()
            else:
                if st.button("✏️ 다시 수정하기", use_container_width=True):
                    st.session_state.review_confirmed = False
                    st.rerun()

# 이미지 품질 (expander로 숨김)
with st.expander("📊 이미지 품질 분석 보기"):
    q = data["quality"]

    q_col1, q_col2, q_col3 = st.columns(3)

    blur_val = q["blur_score"] if q["blur_score"] is not None else "N/A"
    blur_status = "status-good" if q["blur_score"] and q["blur_score"] >= 100 else "status-bad"
    glare_status = "status-bad" if q["glare_detected"] else "status-good"
    res_status = "status-bad" if q["low_resolution_detected"] else "status-good"

    with q_col1:
        st.markdown(f"""
        <div class="quality-card">
            <div class="value {blur_status}">{blur_val}</div>
            <div class="label">🔍 선명도 (Blur Score)</div>
        </div>
        """, unsafe_allow_html=True)

    with q_col2:
        glare_text = "감지됨" if q["glare_detected"] else "정상"
        st.markdown(f"""
        <div class="quality-card">
            <div class="value {glare_status}">{glare_text}</div>
            <div class="label">💡 빛반사 (Glare)</div>
        </div>
        """, unsafe_allow_html=True)

    with q_col3:
        res_text = "부족" if q["low_resolution_detected"] else "정상"
        st.markdown(f"""
        <div class="quality-card">
            <div class="value {res_status}">{res_text}</div>
            <div class="label">📐 해상도</div>
        </div>
        """, unsafe_allow_html=True)

# 전체 OCR 텍스트
if data["ocr"]["raw_text"]:
    with st.expander("📜 전체 OCR 텍스트 보기"):
        st.code(data["ocr"]["raw_text"], language=None)

# 푸터
st.divider()
st.markdown("""
<div style='text-align: center; color: #bbb; font-size: 0.85em; padding: 10px;'>
    Financial Document Review MVP &nbsp;|&nbsp; OCR + Rule-based Pipeline
</div>
""", unsafe_allow_html=True)
