# v1 - Baseline (4-Gate + VLM Fallback)

## Setup
- 4-Gate pipeline: Input Validity > Doc Type > Required Fields > Validation
- Gate 2: keyword ambiguous -> VLM classify (4B)
- Gate 3: review -> VLM reread for missing/low-conf fields
- VLM: Qwen3-VL-4B-Instruct on GPU
- PaddleOCR: GPU (RTX 6000 Ada)
- Char-level confidence extraction via CTC monkey-patch
- 77 samples (11 folders x 7 images)

## Result
| Decision | Count | % |
|----------|-------|---|
| pass | 18 | 23.4% |
| review | 25 | 32.5% |
| retake | 34 | 44.2% |
| invalid | 0 | 0.0% |
| ERROR | 0 | 0.0% |

- Safe Pass Rate: 14/18 (77.8%)
- VLM Call Rate: 58.4% (45/77)
- OCR only: 41.6% (32/77)
- Avg Latency: OCR 2.5s, VLM 3.4s

## Key Findings
- valid folder: 5 pass, 2 review (bank-account(2) missing bank_name, id_images low char conf)
- blur: all 7 retake (quality + keyword missing -> retake rule working)
- invalid_doc_type = 0: VLM mismatch + no strong signal -> retake/review instead of invalid
- ERROR = 0: stable after GPU + dependency fixes
