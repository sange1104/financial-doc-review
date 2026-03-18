import requests
import streamlit as st

API_URL = "http://localhost:8001/api/review"

st.set_page_config(page_title="Document Review", layout="centered")
st.title("Financial Document Review")

uploaded = st.file_uploader("문서 이미지를 업로드하세요", type=["png", "jpg", "jpeg"])

if uploaded:
    st.image(uploaded, caption="업로드된 이미지", use_container_width=True)

    with st.spinner("분석 중..."):
        resp = requests.post(
            API_URL,
            files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type)},
        )

    if resp.status_code != 200:
        st.error(f"API 오류: {resp.status_code} - {resp.text}")
    else:
        data = resp.json()
        decision = data["decision"]

        color = {"pass": "green", "retake": "red", "review": "orange"}[decision]
        st.markdown(f"### 판정: :{color}[{decision.upper()}]")
        st.caption(data["reason"])

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("이미지 품질")
            q = data["quality"]
            st.metric("Blur Score", q["blur_score"])
            st.metric("Glare", "감지됨" if q["glare_detected"] else "없음")
            st.metric("저해상도", "감지됨" if q["low_resolution_detected"] else "없음")

        with col2:
            st.subheader("OCR 결과")
            for field in data["ocr"]["fields"]:
                st.text(f"{field['field_name']}: {field['value']} ({field['confidence']:.2f})")

            if data["ocr"]["raw_text"]:
                with st.expander("전체 OCR 텍스트"):
                    st.code(data["ocr"]["raw_text"])
