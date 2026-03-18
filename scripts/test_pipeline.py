import glob
import json

from app.services.ocr_service import extract_ocr
from app.services.quality_service import evaluate_quality
from app.services.rule_engine import decide

image_paths = glob.glob("samples/glare/*.png") + glob.glob("samples/glare/*.jpg")

for path in sorted(image_paths):
    print(f"\n{'='*60}")
    print(f"FILE: {path}")
    print(f"{'='*60}")

    quality = evaluate_quality(path)
    ocr = extract_ocr(path)
    result = decide(quality, ocr)

    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
