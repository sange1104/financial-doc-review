"""Evaluate all sample images and output results as a markdown table."""
import os
import sys
import glob
from collections import Counter

os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.rule_engine import evaluate_id_card, evaluate_bank_account

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "samples")

results = []

paths = sorted(glob.glob(os.path.join(SAMPLES_DIR, "**/*"), recursive=True))
paths = [p for p in paths if p.lower().endswith((".jpg", ".png", ".jpeg"))]

for i, path in enumerate(paths):
    rel = os.path.relpath(path, SAMPLES_DIR)
    folder = rel.split("/")[0]
    fname = os.path.basename(path)

    is_id = fname.startswith("id_")
    is_bank = fname.startswith("bank-account")
    if not is_id and not is_bank:
        continue

    doc_type = "id_card" if is_id else "bank_account"

    try:
        if is_id:
            resp = evaluate_id_card(path)
        else:
            resp = evaluate_bank_account(path)

        decision = resp.decision.value
        reason = resp.reason[:100] if resp.reason else ""
        fields = [f.field_name for f in resp.ocr.fields]
    except Exception as e:
        decision = "ERROR"
        reason = str(e)[:100]
        fields = []

    results.append({
        "path": rel,
        "folder": folder,
        "file": fname,
        "doc_type": doc_type,
        "decision": decision,
        "fields": ", ".join(fields),
        "reason": reason,
    })

    print(f"[{i+1}/{len(paths)}] {rel} -> {decision}", flush=True)

# Markdown table
print("\n\n## Evaluation Results\n")
print("| # | Image Path | Type | Decision | Fields | Reason |")
print("|---|-----------|------|----------|--------|--------|")
for i, r in enumerate(results, 1):
    print(f"| {i} | `{r['path']}` | {r['doc_type']} | **{r['decision']}** | {r['fields']} | {r['reason']} |")

# Summary by folder
print("\n\n## Summary by Folder\n")
print("| Folder | pass | review | retake | invalid | error | Total |")
print("|--------|------|--------|--------|---------|-------|-------|")
folder_stats: dict[str, Counter] = {}
for r in results:
    folder_stats.setdefault(r["folder"], Counter())[r["decision"]] += 1
for folder in sorted(folder_stats):
    c = folder_stats[folder]
    total = sum(c.values())
    print(f"| {folder} | {c.get('pass',0)} | {c.get('review',0)} | {c.get('retake',0)} | {c.get('invalid_doc_type',0)} | {c.get('ERROR',0)} | {total} |")

# Overall summary
print("\n\n## Overall Summary\n")
decisions = Counter(r["decision"] for r in results)
for d, cnt in sorted(decisions.items()):
    print(f"- **{d}**: {cnt}")
print(f"- **Total**: {len(results)}")
