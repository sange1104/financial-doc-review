# OCRGate Performance Report Summary

## Experiment Timeline

| Version | Key Change | pass | review | retake | Safe Pass Rate | VLM Call % |
|---------|-----------|------|--------|--------|----------------|------------|
| v1 | Baseline (4-Gate + VLM 4B) | 18 | 25 | 34 | 77.8% | 58.4% |
| v2 | Conservative retake policy | 18 | 12 | 47 | 77.8% | 22.1% |
| v3 | VLM reread restored + expanded fields | 20 | 23 | 34 | 80.0% | 53.2% |
| v4 | Name post-processing + nim-pattern | 20 | 23 | 34 | 85.0% | 53.2% |
| v5 | VLM model comparison -> 2B default | 20 | 23 | 34 | 85.0% | 53.2% |
| v6 | Safe pass improvement | 19 | 22 | 36 | **94.7%** | 53.2% |

## Key Metrics (Latest: v6)

- **77 samples** (7 originals x 11 conditions: valid, blur, compression, crop, crop_bottom, crop_top, crop_left, downscale, glare, low_contrast, rotation)
- **Safe Pass Rate: 94.7%** (18/19 passes are correct)
- **Field Accuracy (pass only)**: account_number 100.0%, name 94.7%, id_number 88.9%
- **Avg Latency**: OCR-only 2.5s, VLM 3.3s (2B)
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
- v6: 94.7% -> 2 previously unsafe passes eliminated (reclassified as review/retake)

### Remaining Unsafe Pass (1/19)
1. `compression/id_images`: OCR character confusion (김유스비 -> 김유수미, 960201 -> 950201)

This is a genuine OCR failure on severely compressed input — not fixable by rule tuning.

## VLM Effect (v6)

| Decision | Without VLM | With VLM | Delta |
|----------|-------------|----------|-------|
| pass | 15 | 19 | +4 |
| review | 36 | 22 | -14 |
| retake | 26 | 36 | +10 |

VLM converts 14 reviews -> pass(+4) or retake(+10). Retake increase is desirable — VLM correctly rejects ambiguous images.

## VLM Model Comparison (v6 updated)

| Metric | 2B | 4B | 8B |
|--------|----|----|------|
| Avg Latency | 3.3s | 3.3s | 3.4s |
| Safe Pass Rate | 75% | 75% | 75% |
| Decision: | **Default** | - | - |

Latency gap narrowed vs v5. All models produce identical safe pass rates. 2B remains default.
