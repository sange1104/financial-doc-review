import glob
import json

from app.services.rule_engine import evaluate

image_paths = glob.glob("samples/valid/*.png") + glob.glob("samples/valid/*.jpg")

for path in sorted(image_paths):
    print(f"\n{'='*60}")
    print(f"FILE: {path}")
    print(f"{'='*60}")

    result = evaluate(path)

    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
