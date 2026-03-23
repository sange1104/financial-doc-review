"""valid 샘플로부터 다양한 변형(fail) 이미지를 생성한다."""

import glob
import os

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Transform functions
# ---------------------------------------------------------------------------

def make_crop_top(img, ratio=0.4):
    """상단 40%를 잘라낸다 (하단 60%만 남김)."""
    h = img.shape[0]
    return img[int(h * ratio) :, :]


def make_crop_bottom(img, ratio=0.4):
    """하단 40%를 잘라낸다 (상단 60%만 남김)."""
    h = img.shape[0]
    return img[: int(h * (1 - ratio)), :]


def make_crop_left(img, ratio=0.4):
    """좌측 40%를 잘라낸다 (우측 60%만 남김)."""
    w = img.shape[1]
    return img[:, int(w * ratio) :]


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


def make_blur(img, ksize=31):
    """가우시안 블러 적용."""
    return cv2.GaussianBlur(img, (ksize, ksize), 0)


def make_downscale(img, scale=0.25):
    """해상도를 1/4로 축소한 뒤 원래 크기로 다시 키운다 (저해상도 효과)."""
    h, w = img.shape[:2]
    small = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)


def make_compression(img, quality=5):
    """JPEG 압축 아티팩트를 만든다 (quality 5/100)."""
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    _, buf = cv2.imencode(".jpg", img, encode_param)
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def make_rotation(img, angle=15):
    """15도 회전 (빈 영역은 검정)."""
    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), borderValue=(0, 0, 0))


def make_low_contrast(img, factor=0.3):
    """대비를 크게 낮춘다 (factor=0.3 → 원본의 30% 대비)."""
    mean = np.mean(img, dtype=np.float32)
    result = mean + factor * (img.astype(np.float32) - mean)
    return np.clip(result, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TRANSFORMS = {
    "crop_top": make_crop_top,
    "crop_bottom": make_crop_bottom,
    "crop_left": make_crop_left,
    "glare": make_glare,
    "blur": make_blur,
    "downscale": make_downscale,
    "compression": make_compression,
    "rotation": make_rotation,
    "low_contrast": make_low_contrast,
}

if __name__ == "__main__":
    valid_paths = glob.glob("samples/valid/*.png") + glob.glob("samples/valid/*.jpg")

    if not valid_paths:
        print("No valid samples found in samples/valid/")
        exit(1)

    for name in TRANSFORMS:
        os.makedirs(f"samples/{name}", exist_ok=True)

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
            print(f"  {name:15s} -> {out_path}")

    print("\nDone.")
