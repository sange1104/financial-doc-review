import logging
import os

from transformers import AutoModelForImageTextToText, AutoProcessor
from qwen_vl_utils import process_vision_info

logger = logging.getLogger(__name__)
VLM_MAX_RETRIES = 2

# 로컬 캐시가 있으면 로컬, 없으면 HuggingFace에서 다운로드
VLM_BASE = os.environ.get("VLM_BASE", "/sdc/vissent/huggingface/hub")

AVAILABLE_MODELS_LOCAL = {
    "2B": f"{VLM_BASE}/models--Qwen--Qwen3-VL-2B-Instruct/snapshots",
    "4B": f"{VLM_BASE}/models--Qwen--Qwen3-VL-4B-Instruct/snapshots",
    "8B": f"{VLM_BASE}/models--Qwen--Qwen3-VL-8B-Instruct/snapshots",
}

AVAILABLE_MODELS_HF = {
    "2B": "Qwen/Qwen3-VL-2B-Instruct",
    "4B": "Qwen/Qwen3-VL-4B-Instruct",
    "8B": "Qwen/Qwen3-VL-8B-Instruct",
}

_model = None
_processor = None
_current_model_key = None


def _resolve_model_path(model_key: str) -> str:
    """로컬 snapshot이 있으면 로컬 경로, 없으면 HF model ID를 반환."""
    import glob
    local_path = AVAILABLE_MODELS_LOCAL.get(model_key, "")
    if local_path and os.path.isdir(local_path):
        snapshots = glob.glob(os.path.join(local_path, "*"))
        if snapshots:
            return snapshots[0]
    return AVAILABLE_MODELS_HF[model_key]


def _load_model(model_key: str | None = None):
    global _model, _processor, _current_model_key
    if model_key is None:
        model_key = "4B"

    if _model is not None and _current_model_key == model_key:
        return _model, _processor

    # 기존 모델 해제
    if _model is not None:
        import gc
        import torch
        del _model, _processor
        _model = None
        _processor = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    model_dir = _resolve_model_path(model_key)

    _processor = AutoProcessor.from_pretrained(model_dir)
    import torch
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    _model = AutoModelForImageTextToText.from_pretrained(
        model_dir,
        torch_dtype=torch.bfloat16 if device != "cpu" else torch.float32,
        device_map={"": device},
    )
    _current_model_key = model_key
    return _model, _processor


def set_model(model_key: str):
    """VLM 모델 변경. "2B", "4B", "8B" 중 선택."""
    _load_model(model_key)


def classify_document_type(image_path: str) -> tuple[str, str]:
    """이미지를 보고 문서 유형을 분류한다.

    Returns:
        (type, description) 튜플.
        type: "id_card", "bank_account", 또는 "unknown"
        description: 문서에 대한 한글 설명 (예: '이 문서는 "건강보험 자격확인서"로 보입니다.')
    """
    model, processor = _load_model()

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": f"file://{image_path}"},
                {
                    "type": "text",
                    "text": (
                        "이 이미지의 문서 유형을 분류해주세요.\n\n"
                        "## 분류 기준\n"
                        "- id_card: 주민등록증, 운전면허증 등 신분증\n"
                        "- bank_account: 통장사본, 계좌 관련 문서\n"
                        "- unknown: 위 두 가지에 해당하지 않는 문서\n\n"
                        "## 답변 형식\n"
                        "첫 줄에 분류 결과(id_card, bank_account, unknown 중 하나),\n"
                        "둘째 줄에 이 문서가 무엇인지 한글로 설명해주세요.\n\n"
                        "## 예시\n"
                        "id_card\n"
                        '이 문서는 "주민등록증"으로 보입니다.\n\n'
                        "bank_account\n"
                        '이 문서는 "국민은행 통장사본"으로 보입니다.\n\n'
                        "unknown\n"
                        '이 문서는 "건강보험 자격확인서"로 보입니다.\n\n'
                        "unknown\n"
                        '이 문서는 "급여명세서"로 보입니다.'
                    ),
                },
            ],
        }
    ]

    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    ).to(model.device)

    last_error = None
    for attempt in range(1, VLM_MAX_RETRIES + 1):
        try:
            output_ids = model.generate(**inputs, max_new_tokens=60)
            trimmed = output_ids[0][inputs.input_ids.shape[1]:]
            response = processor.decode(trimmed, skip_special_tokens=True).strip()
            break
        except Exception as e:
            last_error = e
            logger.warning("VLM classify attempt %d/%d failed: %s", attempt, VLM_MAX_RETRIES, e)
    else:
        raise RuntimeError(f"VLM classify failed after {VLM_MAX_RETRIES} attempts: {last_error}") from last_error

    lines = [l.strip() for l in response.splitlines() if l.strip()]
    first_line = lines[0].lower() if lines else ""
    description = lines[1] if len(lines) >= 2 else ""

    if "id_card" in first_line:
        return "id_card", description
    elif "bank_account" in first_line:
        return "bank_account", description
    else:
        return "unknown", description


def reread_fields(image_path: str, fields: list[str]) -> dict[str, dict]:
    """VLM으로 특정 필드를 다시 읽는다.

    Returns:
        {field_name: {"value": str, "readable": bool}} 매핑.
        readable=False면 value는 "unknown".
    """
    model, processor = _load_model()

    field_descriptions = {
        "name": "이름 (예: 홍길동)",
        "id_number": "주민등록번호 (예: 880101-1234567)",
        "address": "주소",
        "issue_date": "발급일 (예: 2020.01.01)",
        "account_number": "계좌번호 (예: 110-123-456789)",
        "bank_name": "은행명 (예: 국민은행)",
    }

    fields_text = "\n".join(
        f"- {f}: {field_descriptions.get(f, f)}"
        for f in fields
    )

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": f"file://{image_path}"},
                {
                    "type": "text",
                    "text": (
                        "이 문서 이미지에서 아래 항목들을 읽어주세요.\n\n"
                        f"## 읽어야 할 항목\n{fields_text}\n\n"
                        "## 중요 규칙\n"
                        "- 명확하게 보이는 값만 읽으세요.\n"
                        "- 추측하지 마세요. 조금이라도 불확실하면 반드시 unknown으로 답하세요.\n"
                        "- 흐리거나 가려진 부분은 unknown입니다.\n\n"
                        "## 답변 형식 (한 줄에 하나씩)\n"
                        "필드명: 값\n\n"
                        "## 예시\n"
                        "name: 홍길동\n"
                        "id_number: unknown\n"
                        "bank_name: 국민은행\n"
                        "account_number: 110-123-456789"
                    ),
                },
            ],
        }
    ]

    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    ).to(model.device)

    last_error = None
    for attempt in range(1, VLM_MAX_RETRIES + 1):
        try:
            output_ids = model.generate(**inputs, max_new_tokens=120)
            trimmed = output_ids[0][inputs.input_ids.shape[1]:]
            response = processor.decode(trimmed, skip_special_tokens=True).strip()
            break
        except Exception as e:
            last_error = e
            logger.warning("VLM reread attempt %d/%d failed: %s", attempt, VLM_MAX_RETRIES, e)
    else:
        raise RuntimeError(f"VLM reread failed after {VLM_MAX_RETRIES} attempts: {last_error}") from last_error

    # 파싱
    result: dict[str, dict] = {}
    for line in response.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if key in fields:
            is_unknown = val.lower() in ("unknown", "없음", "모름", "불명", "")
            result[key] = {
                "value": "unknown" if is_unknown else val,
                "readable": not is_unknown,
            }

    # 요청한 필드 중 응답에 없는 건 unknown 처리
    for f in fields:
        if f not in result:
            result[f] = {"value": "unknown", "readable": False}

    return result
