"""valid 샘플로부터 blur, crop, glare 변형 이미지를 생성한다."""

import glob
import os

import cv2
import numpy as np


def make_blur(img, ksize=31):
    """가우시안 블러 적용."""
    return cv2.GaussianBlur(img, (ksize, ksize), 0)


def make_crop(img, ratio=0.4):
    """이미지의 좌상단 일부만 남긴다 (문서가 잘린 효과)."""
    h, w = img.shape[:2]
    return img[: int(h * ratio), : int(w * ratio)]


def make_glare(img):
    """중앙에 밝은 원형 글레어를 합성한다."""
    result = img.copy()
    h, w = result.shape[:2]
    center = (w // 2, h // 2)
    radius = min(h, w) // 3

    overlay = np.zeros_like(result, dtype=np.float32)
    cv2.circle(overlay, center, radius, (255, 255, 255), -1)
    overlay = cv2.GaussianBlur(overlay, (101, 101), 0)

    result = np.clip(result.astype(np.float32) + overlay * 0.8, 0, 255).astype(np.uint8)
    return result


TRANSFORMS = {
    "blur": make_blur,
    "crop": make_crop,
    "glare": make_glare,
}

if __name__ == "__main__":
    valid_paths = glob.glob("samples/valid/*.png") + glob.glob("samples/valid/*.jpg")

    if not valid_paths:
        print("No valid samples found in samples/valid/")
        exit(1)

    for path in sorted(valid_paths):
        img = cv2.imread(path)
        if img is None:
            print(f"  SKIP (cannot read): {path}")
            continue

        basename = os.path.splitext(os.path.basename(path))[0]
        ext = os.path.splitext(path)[1]

        for name, fn in TRANSFORMS.items():
            out_dir = f"samples/{name}"
            out_path = os.path.join(out_dir, f"{basename}_{name}{ext}")
            result = fn(img)
            cv2.imwrite(out_path, result)
            print(f"  {name:6s} -> {out_path}")

    print("\nDone.")
