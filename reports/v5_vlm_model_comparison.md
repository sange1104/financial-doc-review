# v5 - VLM Model Comparison (2B vs 4B vs 8B)

## Setup
- Tested Qwen3-VL 2B, 4B, 8B on VLM-triggered samples only (41/77)
- Same OCR pipeline, only VLM model differs
- Default model switched to 2B after comparison

## Result (VLM-triggered samples only)

### Decision Distribution
| Decision | 2B | 4B | 8B |
|----------|----|----|------|
| pass | 4 | 4 | 5 |
| review | 19 | 18 | 17 |
| retake | 18 | 19 | 19 |

### Latency
| Model | Avg (s) | Min (s) | Max (s) |
|-------|---------|---------|---------|
| 2B | 2.3 | 1.5 | 4.5 |
| 4B | 3.4 | 2.5 | 8.0 |
| 8B | 5.1 | 3.2 | 12.0 |

### Safe Pass Rate
| Model | Safe | Total Pass | Rate |
|-------|------|------------|------|
| 2B | 3 | 4 | 75.0% |
| 4B | 3 | 4 | 75.0% |
| 8B | 4 | 5 | 80.0% |

## Decision: Use 2B as Default
- 8B slightly better safe pass rate but 2x slower
- 2B vs 4B nearly identical accuracy, 2B 30% faster
- For MVP, 2B provides best latency/accuracy tradeoff
- Can upgrade to 4B/8B for production if needed

## Insight
- VLM model size has diminishing returns for this task
- Document type classification and field reread are relatively simple tasks
- Larger models mainly help with edge cases (severely degraded images)
- 2B is sufficient for the "consistency check" role VLM plays in the pipeline
