# v2 - Conservative Retake Policy

## Change
- VLM mismatch/unknown + no fields -> retake (was review)
- VLM mismatch/unknown + has fields -> Gate 3 (was review)
- Removed glare detection entirely
- Reason: VLM alone shouldn't produce review; unclear images should retake

## Result
| Decision | Count | % |
|----------|-------|---|
| pass | 18 | 23.4% |
| review | 12 | 15.6% |
| retake | 47 | 61.0% |
| invalid | 0 | 0.0% |
| ERROR | 0 | 0.0% |

- Safe Pass Rate: 14/18 (77.8%)
- VLM Call Rate: 22.1% (17/77) -- significant drop
- Avg Latency: lower due to fewer VLM calls

## Insight
- review dropped dramatically (25 -> 12) but retake spiked (34 -> 47)
- Over-conservative: too many good images sent to retake
- VLM call rate dropped to 22% -- good for latency but some cases need VLM reread
- Safe Pass Rate unchanged (77.8%) -- pass quality maintained
- Conclusion: retake policy too aggressive, needs balance
