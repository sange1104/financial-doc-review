# OCRGate

OCR + Rule Engine + VLM fallback 기반 금융 문서 자동 검수 서비스.
신분증 / 통장사본 이미지에 대해 **pass / review / retake / invalid_doc_type** 판정을 제공합니다.

## 문제 정의

- 단순 OCR만으로는 blur, crop, glare 등 품질 저하 이미지에서 오검출/누락이 발생합니다.
- VLM은 정확도 보완에 유리하지만 latency와 cost가 큽니다.
- 따라서 **OCR-first + selective VLM fallback** 구조를 설계했습니다. 대부분의 요청은 OCR만으로 빠르게 처리하고, 애매한 케이스에만 VLM을 호출합니다.

## 주요 기능

- **문서 유형**: 신분증 (주민등록증) / 통장사본
- **4-Gate Validation Pipeline**: 입력 유효성 → 문서 유형 → 필수 필드 → 형식/신뢰도 순차 검증
- **OCR 기반 필드 추출**: PaddleOCR + 글자별 confidence 추출 (CTC decoder monkey-patch)
- **VLM fallback**: 문서 유형 재검증 / 누락·저신뢰 필드 reread (Qwen3-VL-4B)
- **2단계 SSE 스트리밍**: OCR 결과 즉시 전송 → VLM 보완 후속 전송
- **FastAPI API + Streamlit UI**: 업로드 → 실시간 분석 → 결과 시각화 → 필드 수정

## 시스템 아키텍처

```
사용자 이미지 업로드
        │
        ▼
  Gate 1: 입력 유효성 ──── 실패 → retake (OCR 스킵)
        │
        ▼
    OCR 추출 (PaddleOCR)
        │
        ▼
  Gate 2: 문서 유형 ────── 불일치 → invalid_doc_type
        │                   애매 → VLM fallback
        ▼
  Gate 3: 필수 정보 ────── 전부 없음 → retake
        │                   일부 문제 → VLM reread 보완
        ▼
  Gate 4: 형식/신뢰도 ──── 불충분 → review
        │
        ▼
      PASS
```

## 프로젝트 구조

```
financial-doc-review/
├── app/
│   ├── main.py                  # FastAPI entrypoint
│   ├── ui.py                    # Streamlit UI
│   ├── api/
│   │   └── review.py            # REST + SSE streaming endpoints
│   ├── schemas/
│   │   ├── decision.py          # Decision, DocumentReviewResponse
│   │   ├── document.py          # DocumentType enum
│   │   ├── ocr.py               # OCRField, OCRResult
│   │   └── quality.py           # ImageQualityResult
│   └── services/
│       ├── ocr_service.py       # PaddleOCR + field extraction
│       ├── quality_service.py   # blur score, resolution check
│       ├── rule_engine.py       # 4-Gate validation pipeline
│       └── vlm_service.py       # Qwen3-VL inference
├── scripts/
│   ├── generate_samples.py      # 9종 degradation 생성
│   ├── eval_samples.py          # 전체 샘플 평가
│   ├── perf_test.py             # 성능 평가 (7개 metric)
│   └── labeling_ui.py           # Ground truth 라벨링 UI
├── samples/                     # valid + degradation + GT labels
├── reports/                     # 성능 평가 리포트
├── requirements.txt
└── pyproject.toml
```

## 설치 및 실행

### 1. 환경 설정

```bash
conda create -n ocr python=3.10
conda activate ocr
pip install -r requirements.txt
```

VLM 사용 시 추가 설치:
```bash
pip install transformers qwen-vl-utils torch
```

### 2. API 서버 실행

```bash
CUDA_VISIBLE_DEVICES=0 uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### 3. UI 실행

```bash
streamlit run app/ui.py --server.port 8501 --server.address 0.0.0.0
```

### 4. 성능 평가

```bash
# 변형 샘플 생성
python scripts/generate_samples.py

# 전체 평가
CUDA_VISIBLE_DEVICES=0 python scripts/perf_test.py
```

> `--reload` 옵션은 PaddleOCR C++ 백엔드 충돌을 유발하므로 사용하지 않습니다.

## API 명세

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/review/id-card` | 신분증 검증 |
| POST | `/api/review/bank-account` | 통장사본 검증 |
| POST | `/api/review/id-card/stream` | 신분증 검증 (SSE) |
| POST | `/api/review/bank-account/stream` | 통장사본 검증 (SSE) |

### Request

```bash
curl -X POST http://localhost:8001/api/review/id-card \
  -F "file=@id_card.jpg"
```

### Response

```json
{
  "document_type": "id_card",
  "decision": "pass",
  "reason": "모든 필수 정보가 정상적으로 확인되었습니다",
  "quality": {
    "blur_score": 2519.11,
    "glare_detected": false,
    "low_resolution_detected": false,
    "is_acceptable": true
  },
  "ocr": {
    "fields": [
      {"field_name": "name", "value": "홍길순", "confidence": 0.95, "char_confidences": [...]},
      {"field_name": "id_number", "value": "820701-2345678", "confidence": 0.97, "char_confidences": [...]},
      {"field_name": "address", "value": "행복특별시 행복한구 행복로 1길 123", "confidence": 0.92, "char_confidences": [...]},
      {"field_name": "issue_date", "value": "2019.03.01", "confidence": 0.91, "char_confidences": [...]}
    ],
    "raw_text": "주민등록증\n홍길순\n820701-2345678\n..."
  }
}
```

## Decision Policy

| Decision | 의미 | 조건 |
|----------|------|------|
| **pass** | 자동 승인 | 모든 Gate 통과, 필수 필드 확보, confidence 충족 |
| **retake** | 재촬영 요청 | 이미지 품질 불량, OCR 텍스트 부족, 필수 필드 전무 |
| **review** | 담당자 확인 | 일부 필드 누락/저신뢰, 형식 불일치 |
| **invalid_doc_type** | 문서 유형 불일치 | 신분증 엔드포인트에 통장사본 등 (strong OCR signal 필요) |

### 필수 필드

| 문서 | 필드 | Confidence 임계값 |
|------|------|-------------------|
| 신분증 | name, id_number, address, issue_date | 0.6 / 0.7+형식 / 0.5 / 0.5 |
| 통장사본 | name, account_number, bank_name | 0.6 / 0.7 / 0.5 |

## 성능 요약

77개 샘플 (valid 7장 + 9종 degradation) 기준:

| Metric | Value |
|--------|-------|
| Total samples | 77 |
| Safe Pass Rate | 85.0% (17/20) |
| invalid_doc_type | 0건 |
| OCR-only 평균 latency | 2.3s |
| VLM fallback 평균 latency | 3.3s |
| VLM 호출 비율 | 53.2% |
| valid 이미지 pass | 6/7 |

## 제한 사항

- **이름 추출**: bbox 없이 텍스트 순서 기반 heuristic 사용. OCR line order가 깨지면 오인식 가능.
- **은행명 매칭**: 하드코딩된 은행명 리스트와 exact match. OCR 오인식 시 매칭 실패.
- **Glare 감지**: 흰색 문서 배경과 실제 glare 구분이 어려워 비활성화 상태.
- **Crop/Blur**: 심한 crop이나 blur에서는 retake 비율이 높음 (의도된 동작).
- **계좌번호**: exact match가 아닌 service-acceptable partial match 기준이 필요할 수 있음.
