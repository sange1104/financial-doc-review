from transformers import AutoModelForImageTextToText, AutoProcessor
from qwen_vl_utils import process_vision_info

MODEL_PATH = "/sdc/vissent/huggingface/hub/models--Qwen--Qwen3-VL-4B-Instruct/snapshots"

_model = None
_processor = None


def _load_model():
    global _model, _processor
    if _model is None:
        import glob
        import os
        # snapshot 디렉토리 찾기
        snapshots = glob.glob(os.path.join(MODEL_PATH, "*"))
        model_dir = snapshots[0] if snapshots else MODEL_PATH

        _processor = AutoProcessor.from_pretrained(model_dir)
        import torch
        _model = AutoModelForImageTextToText.from_pretrained(
            model_dir,
            torch_dtype=torch.bfloat16,
            device_map={"": "cuda:5"},
        )
    return _model, _processor


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

    output_ids = model.generate(**inputs, max_new_tokens=60)
    trimmed = output_ids[0][inputs.input_ids.shape[1]:]
    response = processor.decode(trimmed, skip_special_tokens=True).strip()

    lines = [l.strip() for l in response.splitlines() if l.strip()]
    first_line = lines[0].lower() if lines else ""
    description = lines[1] if len(lines) >= 2 else ""

    if "id_card" in first_line:
        return "id_card", description
    elif "bank_account" in first_line:
        return "bank_account", description
    else:
        return "unknown", description
