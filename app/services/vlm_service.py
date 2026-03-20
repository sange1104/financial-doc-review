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
        _model = AutoModelForImageTextToText.from_pretrained(
            model_dir,
            torch_dtype="auto",
            device_map="auto",
        )
    return _model, _processor


def classify_document_type(image_path: str) -> str:
    """이미지를 보고 문서 유형을 분류한다.

    Returns:
        "id_card", "bank_account", 또는 "unknown"
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
                        "이 이미지의 문서 유형을 분류해주세요. "
                        "다음 중 하나만 답해주세요:\n"
                        "- id_card (주민등록증, 운전면허증 등 신분증)\n"
                        "- bank_account (통장사본, 계좌 관련 문서)\n"
                        "- unknown (위 두 가지에 해당하지 않는 문서)\n\n"
                        "답변은 id_card, bank_account, unknown 중 하나만 출력하세요."
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

    output_ids = model.generate(**inputs, max_new_tokens=20)
    trimmed = output_ids[0][inputs.input_ids.shape[1]:]
    response = processor.decode(trimmed, skip_special_tokens=True).strip().lower()

    if "id_card" in response:
        return "id_card"
    elif "bank_account" in response:
        return "bank_account"
    else:
        return "unknown"
