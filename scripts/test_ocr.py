import glob
from paddleocr import PaddleOCR

ocr = PaddleOCR(use_textline_orientation=True, lang="korean")

image_paths = glob.glob("samples/valid/*.png") + glob.glob("samples/valid/*.jpg")

for path in sorted(image_paths):
    print(f"\n{'='*60}")
    print(f"FILE: {path}")
    print(f"{'='*60}")

    result = ocr.predict(path)

    for res in result:
        if "rec_texts" in res:
            for text, score in zip(res["rec_texts"], res["rec_scores"]):
                print(f"  [{score:.3f}] {text}")
