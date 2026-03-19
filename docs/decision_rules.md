# Decision Rules

## Overview

The system determines the final decision through a 4-gate pipeline:

- `pass` — 자동 승인
- `retake` — 재촬영 요청
- `review` — 담당자 확인 필요
- `invalid_doc_type` — 잘못된 문서 유형

---

## Decision Philosophy

### Input Quality Failure → `retake`

이 입력으로는 답이 안 나온다.

- 이미지가 물리적으로 부족하여 신뢰할 수 있는 해석이 불가능
- 재촬영 없이는 개선 불가

### Document Type Mismatch → `invalid_doc_type`

잘못된 문서가 올라왔다.

- 신분증 엔드포인트에 통장사본이 들어온 경우
- 통장사본 엔드포인트에 신분증이 들어온 경우

### Uncertainty / Ambiguity → `review`

입력은 쓸 만한데 자동 시스템 확신이 부족하다.

- 필수 필드 일부 누락
- OCR confidence 낮음
- 형식 검증 실패

### All Clear → `pass`

자동 승인 가능한 상태다.

- 문서 유형 적합, 품질 허용 범위, 필수 필드 확보, 형식 검증 통과

---

## 4-Gate Pipeline

```
이미지 입력
    │
    ▼
Gate 1: 입력 유효성 ──── 실패 → retake (OCR 스킵)
    │
    ▼
  OCR 추출
    │
    ▼
Gate 2: 문서 유형 ────── 불일치 → invalid_doc_type
    │
    ▼
Gate 3: 필수 정보 ────── 전부 없음 → retake
    │                     일부 없음 → review
    ▼
Gate 4: 형식 검증 ────── 불충분 → review
    │
    ▼
  PASS
```

---

## Gate 1. 입력 유효성

이미지 자체가 유효한지 검증한다. 여기서 실패하면 OCR을 수행하지 않는다.

| 조건 | 결과 |
|------|------|
| 이미지 파일 읽기 실패 | retake |
| 이미지 크기 100px 미만 | retake |
| 화면이 95% 이상 검은색 | retake |
| 화면이 95% 이상 흰색 | retake |
| blur score < 100 | retake |
| 저해상도 감지 | retake |

---

## Gate 2. 문서 유형 검증

OCR raw text에서 키워드를 탐색하여 문서 유형이 기대와 맞는지 확인한다.

| 상황 | 결과 |
|------|------|
| id-card 엔드포인트 + 통장 키워드만 감지 | invalid_doc_type |
| bank-account 엔드포인트 + 주민등록증 키워드만 감지 | invalid_doc_type |
| 키워드 혼재 또는 판단 불가 | 다음 gate로 진행 |

**ID card 키워드:** 주민등록증, 운전면허, 여권

**Bank account 키워드:** 통장, 계좌, 예금, 은행, Bank

---

## Gate 3. 필수 정보 존재 검증

문서 타입별 필수 필드가 존재하는지 확인한다.

### ID Card 필수 필드
- name (이름)
- id_number (주민등록번호)

### Bank Account 필수 필드
- name (예금주)
- account_number (계좌번호)
- bank_name (은행명)

| 조건 | 결과 |
|------|------|
| OCR 텍스트가 극단적으로 적음 (< 10자) | retake |
| 핵심 필드 전부 누락 (name + 식별번호 둘 다 없음) | retake |
| 일부 필드 누락 | review |

---

## Gate 4. 형식 검증 + 최종 확신

필드의 형식과 신뢰도를 확인한다.

| 조건 | 결과 |
|------|------|
| id_number 형식 불일치 (######-####### 패턴) | review |
| OCR confidence < 0.7 | review |
| 모든 검증 통과 | pass |

---

## Summary Table

| Gate | 조건 | Decision |
|------|------|----------|
| 1 | 이미지 읽기 불가 / 너무 작음 / 검은·흰 화면 / blur / 저해상도 | retake |
| 2 | 문서 유형 불일치 | invalid_doc_type |
| 3 | 필수 필드 전부 없음 | retake |
| 3 | 필수 필드 일부 없음 | review |
| 4 | 형식 불일치 / confidence 낮음 | review |
| — | 전부 통과 | pass |

---

## Notes

- `retake`: 이 입력으로는 답이 안 나온다 → 재촬영 필요
- `invalid_doc_type`: 잘못된 문서 → 올바른 문서 업로드 필요
- `review`: 입력은 쓸 만하지만 확신 부족 → 담당자 확인
- `pass`: 자동 승인 가능
- Gate 1 실패 시 OCR을 스킵하여 불필요한 연산 방지

---

## Future Extensions

- Glare 감지 (현재 비활성화)
- VLM secondary reviewer
- Learned decision model replacing rule-based logic
- Adaptive thresholds based on data distribution
