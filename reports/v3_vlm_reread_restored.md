# v3 - VLM Reread Restored + Required Fields Expanded

## Change
- Restored VLM reread for Gate 3 review cases
- Added address, issue_date to ID card required fields check
- VLM mismatch + no fields -> retake (kept from v2)
- VLM mismatch + has fields -> Gate 3 (kept from v2)
- account_number missing after VLM reread -> retake (new)

## Result
| Decision | Count | % |
|----------|-------|---|
| pass | 20 | 26.0% |
| review | 23 | 29.9% |
| retake | 34 | 44.2% |
| invalid | 0 | 0.0% |
| ERROR | 0 | 0.0% |

- Safe Pass Rate: 16/20 (80.0%) -- improved
- VLM Call Rate: 53.2% (41/77)
- VLM Effect: review -12 (38 -> 26), pass +4, retake +8

## Insight
- Pass increased (18 -> 20) with VLM reread filling missing text fields
- Safe Pass Rate improved (77.8% -> 80.0%)
- retake normalized back to 34 (from 47 in v2)
- VLM reread works: text fields补by VLM, numeric fields conservative
- Remaining unsafe passes: OCR misreads on compressed/cropped images
