# Pipeline Analysis

## 실험 조건

- 샘플: valid 3장 기준으로 blur, crop, glare 변형 생성 (총 12장)
- 파이프라인: quality_service → ocr_service → rule_engine

## 결과

| category | decision | blur_score | glare | lowres | reason |
|----------|----------|-----------|-------|--------|--------|
| valid | pass | 2519.11 | False | False | All required fields present and valid |
| valid | pass | 1935.46 | False | False | All required fields present and valid |
| valid | pass | 2969.24 | False | False | All required fields present and valid |
| blur | retake | 2.40 | False | False | image too blurry (score: 2.4) |
| blur | retake | 1.86 | False | False | image too blurry (score: 1.86) |
| blur | retake | 2.60 | False | False | image too blurry (score: 2.6) |
| crop | review | 2641.60 | False | False | id_number field not found |
| crop | retake | 1416.17 | False | False | OCR extracted too little text from image |
| crop | retake | 2659.89 | False | True | image resolution too low |
| glare | pass | 2068.14 | False | False | All required fields present and valid |
| glare | retake | 1293.62 | True | False | glare detected |
| glare | retake | 2164.23 | True | False | glare detected |

## 분석

### valid (3/3 pass)
- 정상 이미지는 모두 pass. blur score 1900~3000 범위.

### blur (3/3 retake)
- blur score가 1.8~2.6으로 threshold(100) 대비 극단적으로 낮음. 정상 작동.

### crop (1 review, 2 retake)
- crop 정도에 따라 판정이 다름
- id_number만 누락된 경우 → review (이미지 품질은 OK이므로)
- 텍스트 자체가 거의 없는 경우 → retake
- 해상도가 너무 낮은 경우 → retake (low_resolution_detected)

### glare (1 pass, 2 retake)
- 1장이 pass로 판정됨: 합성 glare가 텍스트 영역을 충분히 가리지 못함
- glare 강도 또는 임계값 조정 필요 (현재: pixel > 250 비율 > 30%)

## 개선 포인트

- glare 합성 강도를 높이거나 임계값을 낮추는 실험 필요
- crop에서 review vs retake 경계가 OCR 추출량에 의존 — 의도된 설계이나 문서화 필요
