import cv2
import numpy as np

from app.schemas.quality import ImageQualityResult

BLUR_THRESHOLD = 100.0
MIN_IMAGE_SIZE = 100


def evaluate_quality(image_path: str) -> ImageQualityResult:
    img = cv2.imread(image_path)
    if img is None:
        return ImageQualityResult(
            blur_score=None,
            glare_detected=None,
            low_resolution_detected=None,
            is_acceptable=False,
        )

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # blur: Laplacian variance (낮을수록 흐릿함)
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()

    # glare: 과도하게 밝은 영역 비율
    bright_ratio = np.mean(gray > 250)
    glare_detected = bright_ratio > 0.3

    # low resolution: 이미지가 너무 작으면 텍스트 인식 불가
    low_resolution_detected = h < MIN_IMAGE_SIZE or w < MIN_IMAGE_SIZE

    # 종합 판정
    is_acceptable = (
        blur_score >= BLUR_THRESHOLD
        and not glare_detected
        and not low_resolution_detected
    )

    return ImageQualityResult(
        blur_score=round(blur_score, 2),
        glare_detected=glare_detected,
        low_resolution_detected=low_resolution_detected,
        is_acceptable=is_acceptable,
    )
