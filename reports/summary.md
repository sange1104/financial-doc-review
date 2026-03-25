# OCRGate Performance Report Summary

## Experiment Timeline

| Version | Key Change | pass | review | retake | Safe Pass Rate | VLM Call % |
|---------|-----------|------|--------|--------|----------------|------------|
| v1 | Baseline (4-Gate + VLM 4B) | 18 | 25 | 34 | 77.8% | 58.4% |
| v2 | Conservative retake policy | 18 | 12 | 47 | 77.8% | 22.1% |
| v3 | VLM reread restored + expanded fields | 20 | 23 | 34 | 80.0% | 53.2% |
| v4 | Name post-processing + nim-pattern | 20 | 23 | 34 | **85.0%** | 53.2% |
| v5 | VLM model comparison -> 2B default | 20 | 23 | 34 | 85.0% | 53.2% |

## Key Metrics (Latest: v4/v5)

- **77 samples** (7 originals x 11 conditions: valid, blur, compression, crop, crop_bottom, crop_top, crop_left, downscale, glare, low_contrast, rotation)
- **Safe Pass Rate: 85.0%** (17/20 passes are correct)
- **Field Accuracy (pass only)**: id_number 100%, account_number 90.9%, name 88.2%
- **Avg Latency**: OCR-only 2.5s, VLM 3.4s (4B) / 2.3s (2B)
- **ERROR: 0**, invalid_doc_type: 0

## Evolution of Design Decisions

### VLM Role
- v1: VLM as document classifier + field reread -> too many calls (58%)
- v2: Reduced VLM to only ambiguous cases -> retake spiked (61%)
- v3-v5: VLM as "consistency checker" for gray zone -> balanced (53%)
- Principle: **VLM is a secondary signal, not a primary judge**

### Retake Policy
- v1: Only missing fields -> some bad images got review instead
- v2: Aggressive retake -> UX degraded
- v3-v5: Retake when OCR+VLM both fail -> stable at 44%

### Safe Pass Rate Improvement
- v1: 77.8% -> name space issues, bank name mistaken as person name
- v3: 80.0% -> VLM reread fills missing text fields
- v4: 85.0% -> space stripping + nim-pattern extraction

### Remaining Unsafe Passes (3/20)
1. `compression/bank-account(3)`: severe JPEG compression -> OCR misread name
2. `compression/id_images`: OCR character confusion (유스비 -> 유스미)
3. `crop/bank-account(2)`: name area cropped, account_number truncated

These are genuine OCR failures on severely degraded inputs — cannot be fixed by rule tuning.

## VLM Model Comparison

| Metric | 2B | 4B | 8B |
|--------|----|----|------|
| Avg Latency | **2.3s** | 3.4s | 5.1s |
| Safe Pass Rate | 75% | 75% | 80% |
| Decision: | **Default** | Production | Heavy |

2B selected as default for best latency/accuracy tradeoff in MVP.
