# v4 - Name Post-processing + GT Fix

## Change
- Strip spaces from name field (OCR "시민 존" -> "시민존")
- Add nim-pattern extraction for bank accounts ("홍길동 님" -> "홍길동")
- Prioritize nim-pattern over scoring heuristic (prevents "농협" as name)
- Fix GT: "시민 존" -> "시민존" for consistent comparison
- Name GT comparison now ignores spaces

## Result
| Decision | Count | % |
|----------|-------|---|
| pass | 20 | 26.0% |
| review | 23 | 29.9% |
| retake | 34 | 44.2% |
| invalid | 0 | 0.0% |
| ERROR | 0 | 0.0% |

- Safe Pass Rate: 17/20 (85.0%) -- best so far
- Field accuracy (pass only):
  - id_number: 100%
  - account_number: 90.9%
  - name: 88.2% (was 82.4%)

## Unsafe Pass (3 remaining)
- compression/bank-account(3): name GT='홍길동' OCR='울을' (severe compression)
- compression/id_images: name OCR='김유스미' (OCR misread), id_number off by 1 digit
- crop/bank-account(2): name GT='김투네' OCR='농협' (crop removed name area)

## Insight
- Space stripping eliminated 3 false unsafe cases (시민존)
- Nim-pattern prevents bank name keywords from being mistaken as person name
- Remaining errors are genuine OCR failures on severely degraded images
- Safe Pass Rate: 77.8% -> 80.0% -> 85.0% (steady improvement)
