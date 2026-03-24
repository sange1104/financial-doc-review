import json

import requests
import streamlit as st

API_BASE = "http://localhost:8001/api/review"

FIELD_LABELS = {
    "name": "이름",
    "id_number": "주민등록번호",
    "address": "주소",
    "issue_date": "발급일",
    "account_number": "계좌번호",
    "bank_name": "은행명",
}

REQUIRED_FIELDS = {
    "id_card": ["name", "id_number", "address", "issue_date"],
    "bank_account_doc": ["name", "account_number", "bank_name"],
}

DECISION_CONFIG = {
    "pass": {"label": "PASS", "color": "#16a34a", "bg": "#f0fdf4", "border": "#86efac", "msg": "문서가 정상적으로 확인되었습니다."},
    "retake": {"label": "RETAKE", "color": "#dc2626", "bg": "#fef2f2", "border": "#fca5a5", "msg": "이미지를 다시 촬영해주세요."},
    "review": {"label": "REVIEW", "color": "#d97706", "bg": "#fffbeb", "border": "#fcd34d", "msg": "담당자 확인이 필요합니다."},
    "invalid_doc_type": {"label": "INVALID", "color": "#7c3aed", "bg": "#f5f3ff", "border": "#c4b5fd", "msg": "올바른 문서 유형을 업로드해주세요."},
}

RETAKE_REASONS = {
    "image too blurry": ("이미지가 흐릿합니다", "카메라 초점을 맞추고 흔들리지 않게 촬영해주세요."),
    "image resolution too low": ("해상도가 너무 낮습니다", "더 가까이에서 촬영해주세요."),
    "too small": ("이미지가 너무 작습니다", "문서가 크게 보이도록 촬영해주세요."),
    "nearly all black": ("이미지가 거의 검은색입니다", "밝은 환경에서 다시 촬영해주세요."),
    "nearly all white": ("이미지가 거의 흰색입니다", "문서가 프레임 안에 있는지 확인해주세요."),
    "could not be read": ("파일을 읽을 수 없습니다", "다른 이미지 파일로 시도해주세요."),
    "too little text": ("텍스트를 인식하지 못했습니다", "문서 전체가 보이도록 촬영해주세요."),
    "No required fields": ("필수 정보를 찾을 수 없습니다", "핵심 정보가 보이도록 촬영해주세요."),
    "OCR could not identify": ("문서를 판별할 수 없습니다", "문서 전체가 보이도록 촬영해주세요."),
    "account_number not found after": ("계좌번호를 찾을 수 없습니다", "계좌번호가 선명하게 보이도록 촬영해주세요."),
}

REVIEW_REASONS = {
    "name field not found": "이름을 찾을 수 없습니다",
    "name confidence too low": "이름 인식 신뢰도가 낮습니다",
    "id_number field not found": "주민등록번호를 찾을 수 없습니다",
    "id_number format invalid": "주민등록번호 형식이 올바르지 않습니다",
    "id_number confidence too low": "주민등록번호 인식 신뢰도가 낮습니다",
    "account_number field not found": "계좌번호를 찾을 수 없습니다",
    "account_number confidence too low": "계좌번호 인식 신뢰도가 낮습니다",
    "bank_name field not found": "은행명을 찾을 수 없습니다",
    "bank_name confidence too low": "은행명 인식 신뢰도가 낮습니다",
    "image too blurry": "이미지가 흐릿합니다",
    "image resolution too low": "해상도가 낮습니다",
    "VLM could not determine document type": "문서 유형을 판별할 수 없습니다",
    "VLM detected bank account": "VLM이 통장사본으로 판별",
    "VLM detected ID card": "VLM이 신분증으로 판별",
    "address confidence too low": "주소 인식 신뢰도가 낮습니다",
    "issue_date confidence too low": "발급일 인식 신뢰도가 낮습니다",
    "id_number low confidence chars": "주민등록번호 일부 글자 신뢰도 낮음",
    "account_number low confidence chars": "계좌번호 일부 글자 신뢰도 낮음",
    "name low confidence chars": "이름 일부 글자 신뢰도 낮음",
    "bank_name low confidence chars": "은행명 일부 글자 신뢰도 낮음",
    "address low confidence chars": "주소 일부 글자 신뢰도 낮음",
    "issue_date low confidence chars": "발급일 일부 글자 신뢰도 낮음",
}


def _get_retake_info(reason: str) -> tuple[str, str]:
    for key, (label, guide) in RETAKE_REASONS.items():
        if key.lower() in reason.lower():
            return label, guide
    return "이미지를 다시 촬영해주세요", "문서가 선명하고 전체가 보이도록 촬영해주세요."


def _get_review_reasons_kr(reason: str) -> list[str]:
    parts = [r.strip() for r in reason.split(";")]
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


def _get_low_conf_hint(char_confs: list[dict], threshold: float = 0.7) -> str:
    low = [(i + 1, cc["char"], cc["confidence"]) for i, cc in enumerate(char_confs) if cc["confidence"] < threshold]
    if not low:
        return ""
    parts = [f"**{pos}번째 '{ch}'** ({conf:.0%})" for pos, ch, conf in low]
    return f"확인 필요: {', '.join(parts)}"


# ── Page ──
st.set_page_config(page_title="OCRGate", layout="wide", page_icon="📄")

B1 = "#1E46FA"  # primary
B2 = "#377FF7"  # mid
B3 = "#0A5BE7"  # dark
B4 = "#79A8F9"  # light

st.markdown(f"""
<style>
    .block-container {{ padding-top: 1.2rem; padding-bottom: 0.5rem; max-width: 1200px; }}
    /* Streamlit 기본 헤더 숨김 */
    header[data-testid="stHeader"] {{ display: none !important; }}
    .stApp {{ background: linear-gradient(180deg, #eef2ff 0%, #f8faff 100%); }}

    /* Header bar */
    .hdr {{ display:flex; align-items:center; gap:10px; padding:10px 0; margin-bottom:10px;
            border-bottom:1px solid {B4}30; }}
    .hdr-logo {{ font-size:1.4em; font-weight:800; color:{B1}; }}
    .hdr-sep {{ width:1px; height:20px; background:{B4}60; }}
    .hdr-sub {{ font-size:0.82em; color:{B3}; }}

    /* Decision strip */
    .d-strip {{ display:flex; align-items:center; gap:12px; padding:10px 16px; border-radius:10px; margin-bottom:8px; }}
    .d-chip {{ padding:4px 14px; border-radius:6px; font-weight:700; font-size:0.85em; color:white; }}
    .d-msg {{ font-size:0.82em; }}

    /* Info box */
    .info-box {{ padding:8px 14px; border-radius:8px; font-size:0.82em; margin:4px 0; }}

    /* Field row */
    .fr {{ display:flex; align-items:center; padding:7px 12px; margin:3px 0;
           border-radius:8px; background:white; border:1px solid #e2e8f0; }}
    .fr:hover {{ border-color:{B4}; box-shadow:0 1px 6px rgba(30,70,250,0.06); }}
    .fr-label {{ font-size:0.75em; color:{B3}; font-weight:600; min-width:72px; }}
    .fr-value {{ flex:1; font-size:0.9em; font-weight:600; color:#1e293b; margin:0 8px; }}
    .fr-conf {{ font-size:0.7em; font-weight:600; padding:2px 8px; border-radius:10px; }}
    .fr-conf.h {{ background:#dcfce7; color:#166534; }}
    .fr-conf.m {{ background:#fef3c7; color:#92400e; }}
    .fr-conf.l {{ background:#fee2e2; color:#991b1b; }}

    /* Section */
    .sec {{ font-size:0.95em; font-weight:700; letter-spacing:0.5px;
            color:{B3}; margin:0 0 8px 2px; }}

    /* Quality inline */
    .q-row {{ display:flex; gap:16px; font-size:0.75em; color:#64748b; padding:4px 0; }}
    .q-row b {{ color:#334155; }}
    /* expander 작게 */
    [data-testid="stExpander"] {{ font-size:0.8em; }}
    [data-testid="stExpander"] summary {{ font-size:0.85em; padding:4px 8px; }}
    /* 라디오 버튼 스타일 */
    .stRadio label p {{ color: #1e293b !important; font-weight: 400 !important; }}
    .stRadio [role="radiogroup"] label div[data-testid="stMarkdownContainer"] {{ color: #1e293b !important; }}
    .stRadio input[type="radio"] {{ accent-color: {B1}; }}
    .stRadio [role="radio"] {{ border-color: #94a3b8 !important; background: white !important; }}
    .stRadio [role="radio"][aria-checked="true"] {{ border-color: {B1} !important; background: {B1} !important; }}
    /* text_input 하단 안내 텍스트 숨김 + placeholder 스타일 */
    .stTextInput [data-testid="InputInstructions"] {{ display: none !important; }}
    .stTextInput input::placeholder {{ color: #b0bec5 !important; font-size: 0.85em; }}
</style>
""", unsafe_allow_html=True)

# ── Header ──
st.markdown(f"""
<div class="hdr">
    <span class="hdr-logo">OCRGate</span>
    <span class="hdr-sep"></span>
    <span class="hdr-sub">신분증 · 통장사본 자동 검증</span>
</div>
""", unsafe_allow_html=True)

# ── Upload row ──
c1, c2 = st.columns([1, 3])
with c1:
    doc_type = st.radio("문서", ["신분증", "통장사본"], horizontal=True, label_visibility="collapsed")
with c2:
    uploaded = st.file_uploader("업로드", type=["png", "jpg", "jpeg"], label_visibility="collapsed")

if not uploaded:
    st.markdown(f'<div style="text-align:center;padding:50px;color:{B4};font-size:0.95em;">📄 이미지를 업로드하면 자동 분석이 시작됩니다</div>', unsafe_allow_html=True)
    st.stop()

# ── API call ──
endpoint = f"{API_BASE}/id-card/stream" if doc_type == "신분증" else f"{API_BASE}/bank-account/stream"
cache_key = f"{uploaded.name}_{uploaded.size}_{doc_type}"
if st.session_state.get("_ck") != cache_key:
    st.session_state._ck = cache_key
    st.session_state._cd = None
    st.session_state.rc = False
    st.session_state.ef = {}

if st.session_state._cd is None:
    data = None
    with st.status("분석 중...", expanded=True) as status:
        step = st.empty()
        resp = requests.post(endpoint, files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}, stream=True)
        if resp.status_code != 200:
            st.error(f"API 오류: {resp.status_code}")
            st.stop()
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            ev = json.loads(line[6:])
            if ev["type"] == "progress":
                step.markdown(ev["message"])
            elif ev["type"] == "result":
                data = ev["data"]
            elif ev["type"] == "error":
                st.error(f"오류: {ev['message']}")
                st.stop()
        step.empty()
        status.update(label="완료", state="complete")
    if data is None:
        st.error("응답 없음")
        st.stop()
    st.session_state._cd = data
else:
    data = st.session_state._cd

decision = data["decision"]
cfg = DECISION_CONFIG[decision]
is_review = decision == "review"
is_pass = decision == "pass"
can_edit = is_review or is_pass
if "rc" not in st.session_state:
    st.session_state.rc = False
if "ef" not in st.session_state:
    st.session_state.ef = {}
if "pass_editing" not in st.session_state:
    st.session_state.pass_editing = False

# review: 바로 편집 모드 / pass: 수정 버튼 클릭 후 편집 모드
if is_review:
    editing = not st.session_state.rc
elif is_pass:
    editing = st.session_state.pass_editing
else:
    editing = False

# ── 3-column layout ──
col_img, col_info, col_fields = st.columns([2.5, 3, 3.5], gap="medium")

# ── Image ──
with col_img:
    st.markdown('<div class="sec">이미지</div>', unsafe_allow_html=True)
    st.image(uploaded, use_container_width=True)
    q = data["quality"]
    blur = q["blur_score"] if q["blur_score"] is not None else "—"
    res = "부족" if q["low_resolution_detected"] else "정상"
    with st.expander("이미지 품질", expanded=False):
        st.markdown(f'<div class="q-row"><span>선명도 <b>{blur}</b></span><span>해상도 <b>{res}</b></span></div>', unsafe_allow_html=True)

# ── Decision + Reason ──
with col_info:
    st.markdown('<div class="sec">판정</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="d-strip" style="background:{cfg['bg']};border:1px solid {cfg['border']};">
        <span class="d-chip" style="background:{cfg['color']};">{cfg['label']}</span>
        <span class="d-msg" style="color:{cfg['color']};">{cfg['msg']}</span>
    </div>
    """, unsafe_allow_html=True)

    if decision == "retake":
        label, guide = _get_retake_info(data["reason"])
        st.markdown(f'<div class="info-box" style="background:#fef2f2;border:1px solid #fca5a5;color:#991b1b;"><b>{label}</b><br/><span style="color:#b91c1c;">{guide}</span></div>', unsafe_allow_html=True)
    elif decision == "invalid_doc_type":
        detected = data.get("document_type", "")
        reason = data.get("reason", "")
        if detected == "id_card":
            msg = "신분증이 감지되었습니다. 통장사본을 업로드해주세요."
        elif detected == "bank_account_doc":
            msg = "통장사본이 감지되었습니다. 신분증을 업로드해주세요."
        elif reason:
            msg = reason
        else:
            msg = "문서 유형이 일치하지 않습니다."
        st.markdown(f'<div class="info-box" style="background:#f5f3ff;border:1px solid #c4b5fd;color:#5b21b6;">{msg}</div>', unsafe_allow_html=True)
    elif decision == "review":
        reasons_kr = _get_review_reasons_kr(data["reason"])
        items = "".join(f"<div style='margin:2px 0;'>· {r}</div>" for r in reasons_kr)
        st.markdown(f'<div class="info-box" style="background:#fffbeb;border:1px solid #fcd34d;color:#92400e;">{items}</div>', unsafe_allow_html=True)

    # OCR text — collapsed
    if data["ocr"]["raw_text"]:
        with st.expander("OCR 전체 텍스트", expanded=False):
            st.markdown(f'<pre style="font-size:0.7em;max-height:150px;overflow-y:auto;background:#f8fafc;padding:8px;border-radius:6px;color:#475569;">{data["ocr"]["raw_text"]}</pre>', unsafe_allow_html=True)

# ── Fields ──
with col_fields:
    if editing:
        lbl = "정보 수정"
    elif can_edit and st.session_state.rc:
        lbl = "확인 완료"
    else:
        lbl = "추출 정보"
    st.markdown(f'<div class="sec">{lbl}</div>', unsafe_allow_html=True)

    fields = list(data["ocr"]["fields"])
    if is_review:
        doc_type_key = data.get("document_type", "")
        required = REQUIRED_FIELDS.get(doc_type_key, [])
        existing = {f["field_name"] for f in fields}
        for rn in required:
            if rn not in existing:
                fields.append({"field_name": rn, "value": "", "confidence": 0.0, "char_confidences": []})
        fields = sorted(fields, key=lambda f: f["confidence"])

    for field in fields:
        fn = field["field_name"]
        label = FIELD_LABELS.get(fn, fn)
        conf = field["confidence"]
        cc = field.get("char_confidences", [])
        cls = "h" if conf >= 0.9 else ("m" if conf >= 0.7 else "l")

        if editing:
            ct = f" ({conf:.0%})" if conf > 0 else ""
            edited = st.text_input(
                f"{label}{ct}", value=field["value"] or "", key=f"e_{fn}",
                placeholder="미검출 — 직접 입력" if not field["value"] else "",
            )
            hint = _get_low_conf_hint(cc)
            if hint:
                st.caption(hint)
            st.session_state.ef[fn] = edited

        elif can_edit and st.session_state.rc:
            val = st.session_state.ef.get(fn, field["value"])
            changed = val != field["value"]
            badge = f' <span style="color:{B1};font-size:0.65em;font-weight:700;">수정됨</span>' if changed else ""
            dv = val if val else '<span style="color:#cbd5e1;">미입력</span>'
            st.markdown(f'<div class="fr"><span class="fr-label">{label}{badge}</span><span class="fr-value">{dv}</span><span class="fr-conf {cls}">{conf:.0%}</span></div>', unsafe_allow_html=True)

        else:
            if cc:
                vh = ""
                for c in cc:
                    ch, cv = c["char"], c["confidence"]
                    if cv >= 0.9:
                        vh += ch
                    elif cv >= 0.7:
                        vh += f'<span style="color:#ea580c;">{ch}</span>'
                    elif cv >= 0.5:
                        vh += f'<span style="color:#dc2626;">{ch}</span>'
                    else:
                        vh += f'<span style="background:#dc2626;color:#fff;padding:0 1px;border-radius:2px;">{ch}</span>'
            else:
                vh = field["value"] or '<span style="color:#cbd5e1;">—</span>'
            st.markdown(f'<div class="fr"><span class="fr-label">{label}</span><span class="fr-value">{vh}</span><span class="fr-conf {cls}">{conf:.0%}</span></div>', unsafe_allow_html=True)

    if can_edit:
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        if editing:
            if st.button("확인 완료", type="primary", use_container_width=True):
                st.session_state.rc = True
                st.session_state.pass_editing = False
                st.rerun()
        elif st.session_state.rc:
            if st.button("다시 수정", use_container_width=True):
                st.session_state.rc = False
                if is_pass:
                    st.session_state.pass_editing = True
                st.rerun()
        elif is_pass:
            # pass 초기 상태: 수정 버튼만 표시
            if st.button("수정", use_container_width=True):
                st.session_state.pass_editing = True
                st.rerun()
