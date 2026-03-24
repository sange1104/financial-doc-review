"""Ground truth 라벨링 UI — 이미지를 보며 OCR 필드와 decision을 기록한다."""

import glob
import json
import os

import gradio as gr

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "samples")
LABELS_PATH = os.path.join(SAMPLES_DIR, "ground_truth.json")

# 문서 타입별 필드 정의
FIELDS_BY_DOC_TYPE = {
    "id_card": ["name", "id_number", "address", "issue_date"],
    "bank_account": ["name", "account_number", "bank_name"],
}

DECISIONS = ["pass", "retake", "review", "invalid_doc_type"]


def _scan_images():
    paths = sorted(glob.glob(os.path.join(SAMPLES_DIR, "**", "*"), recursive=True))
    return [p for p in paths if p.lower().endswith((".jpg", ".jpeg", ".png"))]


def _load_labels() -> dict:
    if os.path.exists(LABELS_PATH):
        with open(LABELS_PATH) as f:
            return json.load(f)
    return {}


def _save_labels(labels: dict):
    with open(LABELS_PATH, "w") as f:
        json.dump(labels, f, ensure_ascii=False, indent=2)


def _rel(path: str) -> str:
    return os.path.relpath(path, SAMPLES_DIR)


def _guess_doc_type(filename: str) -> str:
    if filename.startswith("id_"):
        return "id_card"
    if filename.startswith("bank"):
        return "bank_account"
    return "id_card"


# ── state ──
ALL_IMAGES = _scan_images()
LABELS = _load_labels()


def load_item(idx):
    """idx번째 이미지를 로드하여 UI 값을 반환한다."""
    idx = int(idx)
    if idx < 0:
        idx = 0
    if idx >= len(ALL_IMAGES):
        idx = len(ALL_IMAGES) - 1

    path = ALL_IMAGES[idx]
    rel = _rel(path)
    fname = os.path.basename(path)

    saved = LABELS.get(rel, {})
    doc_type = saved.get("doc_type", _guess_doc_type(fname))
    decision = saved.get("decision", "pass")
    fields = saved.get("fields", {})

    labeled_count = sum(1 for img in ALL_IMAGES if _rel(img) in LABELS)
    status = f"{idx + 1} / {len(ALL_IMAGES)}  (labeled: {labeled_count})"

    return (
        idx,
        path,              # image
        status,            # info
        doc_type,
        decision,
        fields.get("name", ""),
        fields.get("id_number", ""),
        fields.get("address", ""),
        fields.get("issue_date", ""),
        fields.get("account_number", ""),
        fields.get("bank_name", ""),
        rel,
    )


def save_and_next(idx, doc_type, decision, name, id_number, address, issue_date,
                  account_number, bank_name):
    idx = int(idx)
    path = ALL_IMAGES[idx]
    rel = _rel(path)

    fields = {}
    if doc_type == "id_card":
        if name:
            fields["name"] = name
        if id_number:
            fields["id_number"] = id_number
        if address:
            fields["address"] = address
        if issue_date:
            fields["issue_date"] = issue_date
    else:
        if name:
            fields["name"] = name
        if account_number:
            fields["account_number"] = account_number
        if bank_name:
            fields["bank_name"] = bank_name

    LABELS[rel] = {"doc_type": doc_type, "decision": decision, "fields": fields}
    _save_labels(LABELS)

    return load_item(idx + 1)


def save_current(idx, doc_type, decision, name, id_number, address, issue_date,
                 account_number, bank_name):
    idx = int(idx)
    path = ALL_IMAGES[idx]
    rel = _rel(path)

    fields = {}
    if doc_type == "id_card":
        if name:
            fields["name"] = name
        if id_number:
            fields["id_number"] = id_number
        if address:
            fields["address"] = address
        if issue_date:
            fields["issue_date"] = issue_date
    else:
        if name:
            fields["name"] = name
        if account_number:
            fields["account_number"] = account_number
        if bank_name:
            fields["bank_name"] = bank_name

    LABELS[rel] = {"doc_type": doc_type, "decision": decision, "fields": fields}
    _save_labels(LABELS)

    return load_item(idx)


def go_prev(idx):
    return load_item(int(idx) - 1)


def go_next(idx):
    return load_item(int(idx) + 1)


# ── UI ──

ALL_OUTPUTS = []  # filled after building


def build_ui():
    with gr.Blocks(title="Ground Truth Labeling", css="""
        .field-row { margin-bottom: 4px !important; }
    """) as app:
        gr.Markdown("## Ground Truth Labeling")

        idx_state = gr.State(value=0)

        with gr.Row():
            with gr.Column(scale=3):
                image = gr.Image(label="Document Image", type="filepath", interactive=False, height=500)
            with gr.Column(scale=2):
                info = gr.Textbox(label="Progress", interactive=False)
                rel_path = gr.Textbox(label="File", interactive=False)
                doc_type = gr.Radio(["id_card", "bank_account"], label="Document Type", value="id_card")
                decision = gr.Radio(DECISIONS, label="Decision", value="pass")

                gr.Markdown("### Common Fields")
                name = gr.Textbox(label="name (이름/예금주)", elem_classes="field-row")

                gr.Markdown("### ID Card Fields")
                id_number = gr.Textbox(label="id_number (주민번호)", elem_classes="field-row")
                address = gr.Textbox(label="address (주소)", elem_classes="field-row")
                issue_date = gr.Textbox(label="issue_date (발급일)", elem_classes="field-row")

                gr.Markdown("### Bank Account Fields")
                account_number = gr.Textbox(label="account_number (계좌번호)", elem_classes="field-row")
                bank_name = gr.Textbox(label="bank_name (은행명)", elem_classes="field-row")

                with gr.Row():
                    prev_btn = gr.Button("< Prev")
                    save_btn = gr.Button("Save", variant="secondary")
                    next_btn = gr.Button("Save & Next >", variant="primary")
                    skip_btn = gr.Button("Next (skip)")

        all_outputs = [idx_state, image, info, doc_type, decision,
                       name, id_number, address, issue_date,
                       account_number, bank_name, rel_path]

        field_inputs = [idx_state, doc_type, decision, name, id_number, address,
                        issue_date, account_number, bank_name]

        next_btn.click(fn=save_and_next, inputs=field_inputs, outputs=all_outputs)
        save_btn.click(fn=save_current, inputs=field_inputs, outputs=all_outputs)
        prev_btn.click(fn=go_prev, inputs=[idx_state], outputs=all_outputs)
        skip_btn.click(fn=go_next, inputs=[idx_state], outputs=all_outputs)

        app.load(fn=lambda: load_item(0), outputs=all_outputs)

    return app


if __name__ == "__main__":
    app = build_ui()
    app.launch(server_name="0.0.0.0", server_port=7860)
