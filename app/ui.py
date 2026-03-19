import requests
import streamlit as st

API_BASE = "http://localhost:8001/api/review"

FIELD_LABELS = {
    "doc_title": "📄 문서 제목",
    "name": "👤 이름",
    "id_number": "🔢 주민등록번호",
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

st.set_page_config(page_title="Document Review", layout="centered", page_icon="🔍")

# 다크모드 감지
is_dark = st.get_option("theme.base") == "dark"

# 글로벌 스타일
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 30px 0 10px 0;
    }
    .title-text { color: #1a237e; }
    .subtitle-badge { background: #e8eaf6; color: #4a148c; }
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
st.markdown("""
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

endpoint = f"{API_BASE}/id-card" if doc_type == "신분증" else f"{API_BASE}/bank-account"

with st.spinner("🔄 문서를 분석하고 있습니다..."):
    resp = requests.post(
        endpoint,
        files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type)},
    )

if resp.status_code != 200:
    st.error(f"API 오류: {resp.status_code} - {resp.text}")
    st.stop()

data = resp.json()
decision = data["decision"]
cfg = DECISION_CONFIG[decision]

# 판정 결과 배너
st.markdown(f"""
<div class="decision-banner" style="background: {cfg['bg']};">
    <h1>{cfg['icon']} {cfg['label']}</h1>
    <p>{cfg['msg']}</p>
</div>
""", unsafe_allow_html=True)

# 사유
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

with col_ocr:
    st.markdown('<div class="section-header">📝 추출된 정보</div>', unsafe_allow_html=True)

    if not data["ocr"]["fields"]:
        st.markdown("""
        <div style='text-align: center; padding: 40px; color: #aaa;'>
            <p style='font-size: 2em;'>🚫</p>
            <p>추출된 필드가 없습니다</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        for field in data["ocr"]["fields"]:
            label = FIELD_LABELS.get(field["field_name"], field["field_name"])
            conf = field["confidence"]
            if conf >= 0.9:
                conf_class = "conf-high"
            elif conf >= 0.7:
                conf_class = "conf-mid"
            else:
                conf_class = "conf-low"

            st.markdown(f"""
            <div class="field-card">
                <div class="field-label">{label}</div>
                <span class="field-value">{field['value']}</span>
                <span class="conf-badge {conf_class}">{conf:.0%}</span>
            </div>
            """, unsafe_allow_html=True)

# 이미지 품질
st.markdown('<div class="section-header">📊 이미지 품질 분석</div>', unsafe_allow_html=True)
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
    st.markdown("")
    with st.expander("📜 전체 OCR 텍스트 보기"):
        st.code(data["ocr"]["raw_text"], language=None)

# 푸터
st.divider()
st.markdown("""
<div style='text-align: center; color: #bbb; font-size: 0.85em; padding: 10px;'>
    Financial Document Review MVP &nbsp;|&nbsp; OCR + Rule-based Pipeline
</div>
""", unsafe_allow_html=True)
