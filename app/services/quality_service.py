import cv2
import numpy as np

from app.schemas.quality import ImageQualityResult

BLUR_THRESHOLD = 100.0
MIN_IMAGE_SIZE = 100
GLARE_SATURATED_RATIO = 0.05


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

    # glare: 포화 영역(255)의 국소 집중도로 판단
    # 문서 배경의 균일한 밝음과 구분하기 위해
    # 포화 영역이 존재하면서 그 주변에 밝기 변화가 급격한 경우 glare로 판단
    saturated_mask = (gray == 255).astype(np.uint8)
    saturated_ratio = np.mean(saturated_mask)

    if saturated_ratio > GLARE_SATURATED_RATIO:
        # 포화 영역의 경계에서 gradient가 강한지 확인
        gradient = cv2.Sobel(gray, cv2.CV_64F, 1, 1)
        grad_at_edge = cv2.dilate(saturated_mask, None) - saturated_mask
        if np.sum(grad_at_edge) > 0:
            mean_grad = np.mean(np.abs(gradient[grad_at_edge > 0]))
            glare_detected = mean_grad > 30
        else:
            glare_detected = False
    else:
        glare_detected = False

    # low resolution: 이미지가 너무 작으면 텍스트 인식 불가
    low_resolution_detected = h < MIN_IMAGE_SIZE or w < MIN_IMAGE_SIZE

    # 종합 판정: blur, 저해상도, glare는 기록만 하고 OCR 결과와 조합하여 판단
    # is_acceptable은 Gate 1에서 파일 읽기/크기/black/white 같은 치명적 문제만 반영
    is_acceptable = True

    return ImageQualityResult(
        blur_score=round(blur_score, 2),
        glare_detected=glare_detected,
        low_resolution_detected=low_resolution_detected,
        is_acceptable=is_acceptable,
    )
