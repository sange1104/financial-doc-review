# v6 - Safe Pass Rate Improvement (94.7%)

## Setup
- 77 samples (7 originals x 11 conditions)
- VLM default: 2B
- Date: 2025-03-25

## Result

### Decision Distribution
| Decision | Count | % |
|----------|-------|---|
| pass | 19 | 24.7% |
| review | 22 | 28.6% |
| retake | 36 | 46.8% |
| invalid_doc_type | 0 | 0.0% |
| ERROR | 0 | 0.0% |

### Safe Pass Rate
**18/19 (94.7%)** (v5: 85.0%)

| Field | Correct | Total | Accuracy |
|-------|---------|-------|----------|
| account_number | 10 | 10 | 100.0% |
| id_number | 8 | 9 | 88.9% |
| name | 18 | 19 | 94.7% |

### Latency
| Path | Count | Avg (s) | Min (s) | Max (s) |
|------|-------|---------|---------|---------|
| ocr_only | 36 | 2.5 | 0.0 | 3.5 |
| vlm_called | 41 | 3.3 | 2.6 | 7.7 |

### VLM Call Rate
- OCR only: 36 (46.8%)
- VLM called: 41 (53.2%)

## Changes from v5

### Safe Pass Rate: 85.0% -> 94.7%
- Previously 3 unsafe passes, now only 1
- Eliminated: `compression/bank-account(3)` name misread
- Eliminated: `crop/bank-account(2)` name/account_number truncation
- 1 pass removed (20->19) — likely reclassified as review/retake

### Remaining Unsafe Pass (1/19)
- `compression/id_images_compression.jpg`: name GT='김유스비' OCR='김유수미', id_number GT='960201-1234567' OCR='950201-1234567'
- Genuine OCR character confusion on compressed image — not fixable by rule tuning

## Per-folder Summary

| Folder | pass | review | retake | invalid | Avg Latency |
|--------|------|--------|--------|---------|-------------|
| blur | 0 | 0 | 7 | 0 | 2.5s |
| compression | 3 | 0 | 4 | 0 | 4.0s |
| crop | 0 | 1 | 6 | 0 | 2.2s |
| crop_bottom | 3 | 4 | 0 | 0 | 2.9s |
| crop_left | 0 | 2 | 5 | 0 | 3.1s |
| crop_top | 0 | 2 | 5 | 0 | 3.0s |
| downscale | 0 | 2 | 5 | 0 | 3.1s |
| glare | 1 | 4 | 2 | 0 | 2.9s |
| low_contrast | 3 | 4 | 0 | 0 | 2.8s |
| rotation | 3 | 2 | 2 | 0 | 2.8s |
| valid | 6 | 1 | 0 | 0 | 2.6s |

## Top Failure Modes

| Mode | Count |
|------|-------|
| retake: account_number not found after OCR + VLM reread | 10 |
| retake: No required fields (account_number, name) could be extracted | 6 |
| review: account_number confidence too low (0.50) | 6 |
| retake: OCR extracted too little text from image | 3 |
| retake: No required fields (name, id_number) could be extracted | 3 |
| review: name field not found | 3 |

## VLM Effect

| Decision | Without VLM | With VLM | Delta |
|----------|-------------|----------|-------|
| pass | 15 | 19 | +4 |
| review | 36 | 22 | -14 |
| retake | 26 | 36 | +10 |

VLM converts 14 reviews into either pass(+4) or retake(+10). The retake increase is desirable — VLM correctly identifies images that OCR alone would leave in ambiguous "review" state.

## VLM Model Comparison (updated)

| Decision | 2B | 4B | 8B |
|----------|------|------|------|
| pass | 4 | 4 | 4 |
| review | 18 | 17 | 17 |
| retake | 19 | 20 | 20 |

| Model | Avg (s) | Min (s) | Max (s) |
|-------|---------|---------|---------|
| 2B | 3.3 | 2.5 | 6.4 |
| 4B | 3.3 | 2.6 | 5.0 |
| 8B | 3.4 | 2.5 | 6.9 |

All models: Safe Pass Rate 75.0% (3/4). Latency gap narrowed vs v5 — 2B remains default.
