# OCRGate

OCR + Rule Engine + VLM fallback 기반 금융 문서 자동 검수 서비스.
신분증 / 통장사본 이미지에 대해 **pass / review / retake / invalid_doc_type** 판정을 제공합니다.

> 📄 [Report](https://sange1104.github.io/financial-doc-review/portfolio/index.html)


### 문제 정의

- 단순 OCR만으로는 blur, crop, glare 등 품질 저하 이미지에서 오검출/누락이 발생합니다.
- VLM은 정확도 보완에 유리하지만 latency와 cost가 큽니다.
- 따라서 **OCR-first + selective VLM fallback** 구조를 설계했습니다. 대부분의 요청은 OCR만으로 빠르게 처리하고, 애매한 케이스에만 VLM을 호출합니다.


### 주요 기능

- **문서 유형**: 신분증 (주민등록증) / 통장사본
- **4-Gate Validation Pipeline**: 입력 유효성 → 문서 유형 → 필수 필드 → 형식/신뢰도 순차 검증
- **OCR 기반 필드 추출**: PaddleOCR + 글자별 confidence 추출 (CTC decoder monkey-patch)
- **VLM fallback**: 문서 유형 재검증 / 누락·저신뢰 필드 reread (Qwen3-VL-2B)
- **2단계 SSE 스트리밍**: OCR 결과 즉시 전송 → VLM 보완 후속 전송
- **FastAPI API + Streamlit UI**: 업로드 → 실시간 분석 → 결과 시각화 → 필드 수정

### 시스템 아키텍처

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

### 프로젝트 구조

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
├── portfolio/
│   └── index.html               # 포트폴리오 (설계·평가·인사이트)
├── requirements.txt
└── pyproject.toml
```

### 설치 및 실행

#### 요구 사항

- Python 3.10
- CUDA 11.8 + cuDNN (GPU 사용 시)
- 약 4GB 디스크 (PaddleOCR 모델 자동 다운로드)

#### 1. 환경 설정

```bash
conda create -n ocr python=3.10
conda activate ocr

# PyTorch (GPU)
pip install torch==2.4.1+cu118 torchvision==0.19.1+cu118 \
  --index-url https://download.pytorch.org/whl/cu118

# PaddlePaddle GPU — PyPI에 3.0.0 GPU 버전이 없으므로 아래 중 택 1:
# (a) PaddlePaddle 공식 인덱스
pip install paddlepaddle-gpu==3.0.0 \
  -f https://www.paddlepaddle.org.cn/whl/linux/cudnn/stable.html
# (b) CPU만 사용 시
pip install paddlepaddle==3.0.0

# 나머지 의존성
pip install -r requirements.txt

# 프로젝트 패키지 설치 (from app.* import 해결)
pip install -e .
```

#### 2. VLM 설정 (선택)

VLM 없이도 OCR-only로 동작합니다. VLM fallback을 사용하려면:

```bash
pip install transformers qwen-vl-utils accelerate
```

로컬에 모델이 있으면 `VLM_BASE` 환경변수로 경로 지정:
```bash
export VLM_BASE=/path/to/huggingface/hub
# 예: /path/to/hub/models--Qwen--Qwen3-VL-4B-Instruct/snapshots/...
```

설정하지 않으면 HuggingFace에서 자동 다운로드합니다 (최초 실행 시 ~8GB).

#### 3. API 서버 실행

```bash
CUDA_VISIBLE_DEVICES=0 uvicorn app.main:app --host 0.0.0.0 --port 8001
```

#### 4. UI 실행

```bash
streamlit run app/ui.py --server.port 8501 --server.address 0.0.0.0
```

#### 5. 성능 평가

```bash
# 변형 샘플 생성
python scripts/generate_samples.py

# 전체 평가
CUDA_VISIBLE_DEVICES=0 python scripts/perf_test.py
```

> `--reload` 옵션은 PaddleOCR C++ 백엔드 충돌을 유발하므로 사용하지 않습니다.

### API 명세

#### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/review/id-card` | 신분증 검증 |
| POST | `/api/review/bank-account` | 통장사본 검증 |
| POST | `/api/review/id-card/stream` | 신분증 검증 (SSE) |
| POST | `/api/review/bank-account/stream` | 통장사본 검증 (SSE) |

#### Request

```bash
curl -X POST http://localhost:8001/api/review/id-card \
  -F "file=@id_card.jpg"
```

#### Response

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
      {"field_name": "name", "value": "홍길순", "confidence": 0.95,
       "char_confidences": [{"char": "홍", "confidence": 0.98}, {"char": "길", "confidence": 0.96}, {"char": "순", "confidence": 0.91}]},
      {"field_name": "id_number", "value": "820701-2345678", "confidence": 0.97, "char_confidences": [...]},
      {"field_name": "address", "value": "행복특별시 행복한구 행복로 1길 123", "confidence": 0.92, "char_confidences": [...]},
      {"field_name": "issue_date", "value": "2019.03.01", "confidence": 0.91, "char_confidences": [...]}
    ],
    "raw_text": "주민등록증\n홍길순\n820701-2345678\n..."
  }
}
```

#### Response 필드 상세

| 필드 | 타입 | 값 범위 | 설명 |
|------|------|---------|------|
| `document_type` | string | `"id_card"` \| `"bank_account_doc"` \| `"unknown"` | 감지된 문서 유형 |
| `decision` | string | `"pass"` \| `"retake"` \| `"review"` \| `"invalid_doc_type"` | 최종 판정 |
| `reason` | string | 자유 텍스트 | 판정 사유 (한글 또는 영문) |
| **quality** | | | |
| `quality.blur_score` | float \| null | 0~∞ (높을수록 선명) | Laplacian variance. `< 100` → blur 판정 |
| `quality.glare_detected` | bool \| null | 항상 `false` (MVP) | 글레어 감지 (현재 비활성) |
| `quality.low_resolution_detected` | bool | `true` \| `false` | 가로 또는 세로 `< 100px` |
| `quality.is_acceptable` | bool | `true` \| `false` | blur + resolution 종합 판단 |
| **ocr** | | | |
| `ocr.fields[]` | array | | 구조화된 필드 목록 |
| `ocr.fields[].field_name` | string | 신분증: `"name"` `"id_number"` `"address"` `"issue_date"` <br> 통장: `"name"` `"account_number"` `"bank_name"` | 필드 식별자 |
| `ocr.fields[].value` | string \| null | | 추출된 값. 추출 실패 시 `null` |
| `ocr.fields[].confidence` | float | 0.0~1.0 | 라인 단위 OCR 신뢰도 |
| `ocr.fields[].char_confidences[]` | array | `[{"char": "홍", "confidence": 0.98}, ...]` | 글자별 신뢰도 (CTC decoder 기반) |
| `ocr.raw_text` | string \| null | | PaddleOCR 전체 인식 텍스트 |

#### Response → Gate 영향도

각 Response 필드가 어떤 Gate의 판정에 사용되는지를 나타냅니다.

```
                          Gate 1       Gate 2       Gate 3       Gate 4
                          입력유효성   문서유형     필수정보     형식/신뢰도
                          ─────────    ─────────    ─────────    ─────────
quality.blur_score           ◈            ◇
quality.low_resolution       ◈            ◇
quality.is_acceptable        ◈            ◇

ocr.raw_text                              ◈            ◇
ocr.raw_text 내 키워드                    ◈
ocr.raw_text 길이                                      ◈

ocr.fields[].value                                     ◈            ◈
ocr.fields[].confidence                                ◇            ◈
ocr.fields[].char_confidences                                       ◈

◈ = 판정에 직접 영향 (이 값에 따라 decision이 바뀜)
◇ = 간접 참조 (판정 보조 또는 조건부 사용)
```

| 필드 | 영향 Gate | 영향 방식 |
|------|-----------|-----------|
| `quality.blur_score` | Gate 1, 2 | `< 100` → Gate 1에서 quality flag 기록. Gate 2에서 ambiguous + blur → **retake** |
| `quality.low_resolution` | Gate 1, 2 | `< 100px` → Gate 1에서 flag. Gate 2에서 ambiguous + low_res → **retake** |
| `ocr.raw_text` (키워드) | Gate 2 | `"주민등록증"` 등 키워드 존재 → 문서 유형 판별. 불일치 → **invalid_doc_type** |
| `ocr.raw_text` (길이) | Gate 3 | `< 10자` → **retake** |
| `ocr.fields[].value` (존재 여부) | Gate 3 | 필수 필드 전무 → **retake**, 일부 누락 → VLM reread → **review** |
| `ocr.fields[].confidence` | Gate 3, 4 | 필드 신뢰도 임계값 미달 → VLM reread 대상 (Gate 3) 또는 **review** (Gate 4) |
| `ocr.fields[].char_confidences` | Gate 4 | 글자별 `< 0.5` → **review** |
| `id_number` 형식 | Gate 4 | `\d{6}-\d{7}` 불일치 → **review** |

### Decision Policy

| Decision | 의미 | 조건 |
|----------|------|------|
| **pass** | 자동 승인 | 모든 Gate 통과, 필수 필드 확보, confidence 충족 |
| **retake** | 재촬영 요청 | 이미지 품질 불량, OCR 텍스트 부족, 필수 필드 전무 |
| **review** | 담당자 확인 | 일부 필드 누락/저신뢰, 형식 불일치 |
| **invalid_doc_type** | 문서 유형 불일치 | 신분증 엔드포인트에 통장사본 등 (strong OCR signal 필요) |

#### 필수 필드

| 문서 | 필드 | Confidence 임계값 |
|------|------|-------------------|
| 신분증 | name, id_number, address, issue_date | 0.6 / 0.7+형식 / 0.5 / 0.5 |
| 통장사본 | name, account_number, bank_name | 0.6 / 0.7 / 0.5 |

### 에러 처리 및 재시도

#### 재시도 정책

| 컴포넌트 | 최대 재시도 | 실패 시 동작 |
|----------|------------|-------------|
| **OCR** (PaddleOCR) | 2회 | `RuntimeError` → 503 응답 |
| **VLM** (classify_document_type) | 2회 | `RuntimeError` → 503 응답 |
| **VLM** (reread_fields) | 2회 | `RuntimeError` → 503 응답 |

#### HTTP 상태 코드

| 상태 코드 | 상황 | 클라이언트 대응 |
|-----------|------|----------------|
| **200** | 정상 처리 (pass/retake/review/invalid 모두 포함) | 응답의 `decision` 필드로 분기 |
| **400** | 이미지가 아닌 파일 업로드 | 파일 형식 확인 후 재요청 |
| **503** | OCR/VLM 재시도 전부 실패 (GPU 과부하 등) | 잠시 후 재시도 |
| **500** | 예상치 못한 내부 에러 | 관리자 확인 필요 |

#### SSE 스트리밍 에러

```json
{"type": "error", "message": "OCR failed after 2 attempts: ...", "retryable": true}
{"type": "error", "message": "Internal error: ValueError", "retryable": false}
```

- `retryable: true` — 일시적 실패 (OCR/VLM 재시도 소진). 클라이언트가 재요청 가능
- `retryable: false` — 내부 에러. 재시도해도 동일 실패 가능성 높음

### 성능 요약

77개 샘플 (valid 7장 + 9종 degradation) 기준:

| Metric | Value |
|--------|-------|
| Total samples | 77 |
| Safe Pass Rate | 94.7% (18/19) |
| invalid_doc_type | 0건 |
| OCR-only 평균 latency | 2.5s |
| VLM fallback 평균 latency | 3.3s |
| VLM 호출 비율 | 53.2% |
| valid 이미지 pass | 6/7 |

### 추후 개선 사항

- **이름 추출**: bbox 없이 텍스트 순서 기반 heuristic 사용. OCR line order가 깨지면 오인식 가능.
- **은행명 매칭**: 하드코딩된 은행명 리스트와 exact match. OCR 오인식 시 매칭 실패.
- **Glare 감지**: 흰색 문서 배경과 실제 glare 구분이 어려워 비활성화 상태.
- **Crop/Blur**: 심한 crop이나 blur에서는 retake 비율이 높음 (의도된 동작).
- **계좌번호**: exact match가 아닌 service-acceptable partial match 기준이 필요할 수 있음.
