"""Performance test: decision distribution, latency, VLM call rate, failure modes,
safe pass rate, VLM effect quantification."""
import os
import sys
import glob
import json
import time
from collections import Counter, defaultdict

os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.rule_engine import evaluate_id_card, evaluate_bank_account

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "samples")

# Ground truth
GT_PATH = os.path.join(SAMPLES_DIR, "ground_truth.json")
with open(GT_PATH) as f:
    GT = json.load(f)

# 핵심 필드 (Safe Pass Rate 평가 대상)
CRITICAL_FIELDS = {
    "id_card": ["name", "id_number"],
    "bank_account": ["name", "account_number"],
}

paths = sorted(glob.glob(os.path.join(SAMPLES_DIR, "**/*"), recursive=True))
paths = [p for p in paths if p.lower().endswith((".jpg", ".png", ".jpeg"))]

results = []
vlm_calls = {"ocr_only": 0, "vlm_called": 0}
latencies = {"ocr_only": [], "vlm_called": []}
failure_modes = defaultdict(list)  # reason -> [file]

for i, path in enumerate(paths):
    rel = os.path.relpath(path, SAMPLES_DIR)
    fname = os.path.basename(path)
    is_id = fname.startswith("id_")
    is_bank = fname.startswith("bank-account")
    if not is_id and not is_bank:
        continue

    evaluate_fn = evaluate_id_card if is_id else evaluate_bank_account
    vlm_tracker = {"called": False}

    def track_progress(msg):
        if "VLM" in msg:
            vlm_tracker["called"] = True

    try:
        t0 = time.time()
        resp = evaluate_fn(path, on_progress=track_progress)
        elapsed = time.time() - t0

        decision = resp.decision.value
        reason = resp.reason[:80] if resp.reason else ""
        n_fields = len(resp.ocr.fields)
        extracted = {f.field_name: f.value for f in resp.ocr.fields}
    except Exception as e:
        elapsed = time.time() - t0
        decision = "ERROR"
        reason = str(e)[:80]
        n_fields = 0
        extracted = {}

    tag = "vlm_called" if vlm_tracker["called"] else "ocr_only"
    vlm_calls[tag] += 1
    latencies[tag].append(elapsed)

    if decision not in ("pass",):
        failure_modes[f"{decision}: {reason}"].append(rel)

    doc_type = "id_card" if is_id else "bank_account"
    results.append({
        "path": rel,
        "doc_type": doc_type,
        "decision": decision,
        "vlm": vlm_tracker["called"],
        "latency": elapsed,
        "fields": n_fields,
        "extracted": extracted,
        "reason": reason,
    })

    status = f"VLM" if vlm_tracker["called"] else "OCR"
    print(f"[{i+1}/{len(paths)}] {elapsed:5.1f}s {status:3s} {decision:16s} {rel}", flush=True)

total = len(results)

# ── 1. Decision Distribution ──
print("\n\n## 1. Decision Distribution\n")
decisions = Counter(r["decision"] for r in results)
print("| Decision | Count | % |")
print("|----------|-------|---|")
for d in ["pass", "review", "retake", "invalid_doc_type", "ERROR"]:
    cnt = decisions.get(d, 0)
    pct = cnt / total * 100 if total else 0
    print(f"| {d} | {cnt} | {pct:.1f}% |")
print(f"| **Total** | **{total}** | |")

# ── 2. Latency by Path ──
print("\n\n## 2. Latency by Path\n")
print("| Path | Count | Avg (s) | Min (s) | Max (s) |")
print("|------|-------|---------|---------|---------|")
for tag in ["ocr_only", "vlm_called"]:
    lats = latencies[tag]
    if lats:
        print(f"| {tag} | {len(lats)} | {sum(lats)/len(lats):.1f} | {min(lats):.1f} | {max(lats):.1f} |")

all_lats = latencies["ocr_only"] + latencies["vlm_called"]
if all_lats:
    print(f"| **total** | **{len(all_lats)}** | **{sum(all_lats)/len(all_lats):.1f}** | **{min(all_lats):.1f}** | **{max(all_lats):.1f}** |")

# ── 3. VLM Call Rate ──
print("\n\n## 3. VLM Call Rate\n")
ocr_cnt = vlm_calls["ocr_only"]
vlm_cnt = vlm_calls["vlm_called"]
print(f"- OCR only: {ocr_cnt} ({ocr_cnt/total*100:.1f}%)")
print(f"- VLM called: {vlm_cnt} ({vlm_cnt/total*100:.1f}%)")

# By decision
print("\n| Decision | OCR only | VLM called |")
print("|----------|----------|------------|")
for d in ["pass", "review", "retake", "invalid_doc_type", "ERROR"]:
    ocr_d = sum(1 for r in results if r["decision"] == d and not r["vlm"])
    vlm_d = sum(1 for r in results if r["decision"] == d and r["vlm"])
    print(f"| {d} | {ocr_d} | {vlm_d} |")

# ── 4. Failure Mode Analysis ──
print("\n\n## 4. Failure Mode Analysis\n")
print("| Mode | Count | Examples |")
print("|------|-------|----------|")
for mode, files in sorted(failure_modes.items(), key=lambda x: -len(x[1])):
    examples = ", ".join(files[:3])
    if len(files) > 3:
        examples += f" (+{len(files)-3})"
    print(f"| {mode} | {len(files)} | {examples} |")

# ── 5. Per-folder Summary ──
print("\n\n## 5. Per-folder Summary\n")
print("| Folder | Total | pass | review | retake | invalid | error | Avg Latency |")
print("|--------|-------|------|--------|--------|---------|-------|-------------|")
folder_data = defaultdict(list)
for r in results:
    folder = r["path"].split("/")[0]
    folder_data[folder].append(r)
for folder in sorted(folder_data):
    items = folder_data[folder]
    dc = Counter(r["decision"] for r in items)
    avg_lat = sum(r["latency"] for r in items) / len(items)
    print(f"| {folder} | {len(items)} | {dc.get('pass',0)} | {dc.get('review',0)} | {dc.get('retake',0)} | {dc.get('invalid_doc_type',0)} | {dc.get('ERROR',0)} | {avg_lat:.1f}s |")

# ── 6. Safe Pass Rate ──
print("\n\n## 6. Safe Pass Rate (GT 기반)\n")
pass_results = [r for r in results if r["decision"] == "pass"]
safe_count = 0
unsafe_details = []
field_accuracy = defaultdict(lambda: {"correct": 0, "total": 0})

for r in pass_results:
    gt = GT.get(r["path"])
    if not gt:
        continue

    critical = CRITICAL_FIELDS.get(r["doc_type"], [])
    all_correct = True

    for fname in critical:
        gt_val = gt["fields"].get(fname, "")
        ocr_val = r["extracted"].get(fname, "")
        field_accuracy[fname]["total"] += 1
        # name 필드는 공백 제거 후 비교
        if fname == "name":
            gt_cmp = gt_val.replace(" ", "").strip()
            ocr_cmp = ocr_val.replace(" ", "").strip()
        else:
            gt_cmp = gt_val.strip()
            ocr_cmp = ocr_val.strip()
        if gt_cmp and ocr_cmp and gt_cmp == ocr_cmp:
            field_accuracy[fname]["correct"] += 1
        elif gt_val:
            all_correct = False
            unsafe_details.append(f"{r['path']}: {fname} GT='{gt_val}' OCR='{ocr_val}'")

    if all_correct:
        safe_count += 1

pass_total = len(pass_results)
safe_rate = safe_count / pass_total * 100 if pass_total else 0
print(f"**Safe Pass Rate: {safe_count}/{pass_total} ({safe_rate:.1f}%)**\n")
print(f"= (pass AND 핵심 필드 정확) / pass 전체\n")

print("### 필드별 정확도 (pass 케이스만)\n")
print("| Field | Correct | Total | Accuracy |")
print("|-------|---------|-------|----------|")
for fname in sorted(field_accuracy):
    fa = field_accuracy[fname]
    acc = fa["correct"] / fa["total"] * 100 if fa["total"] else 0
    print(f"| {fname} | {fa['correct']} | {fa['total']} | {acc:.1f}% |")

if unsafe_details:
    print("\n### Unsafe Pass 상세\n")
    print("| 파일 | 필드 | GT | OCR |")
    print("|------|------|----|-----|")
    for d in unsafe_details:
        # parse: "path: field GT='x' OCR='y'"
        parts = d.split(": ", 1)
        path = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
        fname = rest.split(" ")[0] if rest else ""
        gt_part = rest.split("GT='")[1].split("'")[0] if "GT='" in rest else ""
        ocr_part = rest.split("OCR='")[1].split("'")[0] if "OCR='" in rest else ""
        print(f"| {path} | {fname} | {gt_part} | {ocr_part} |")

# ── 7. VLM Effect Quantification ──
print("\n\n## 7. VLM Effect Quantification\n")
print("VLM 없이 (skip_vlm=True) 전체 샘플을 재평가하여 비교합니다...\n")

no_vlm_results = []
for i, path in enumerate(paths):
    rel = os.path.relpath(path, SAMPLES_DIR)
    fname = os.path.basename(path)
    is_id = fname.startswith("id_")
    is_bank = fname.startswith("bank-account")
    if not is_id and not is_bank:
        continue

    evaluate_fn = evaluate_id_card if is_id else evaluate_bank_account
    try:
        resp = evaluate_fn(os.path.join(SAMPLES_DIR, rel), skip_vlm=True)
        dec = resp.decision.value
    except Exception:
        dec = "ERROR"
    no_vlm_results.append({"path": rel, "decision": dec})

vlm_decisions = Counter(r["decision"] for r in results)
no_vlm_decisions = Counter(r["decision"] for r in no_vlm_results)

print("| Decision | Without VLM | With VLM | Delta |")
print("|----------|-------------|----------|-------|")
for d in ["pass", "review", "retake", "invalid_doc_type", "ERROR"]:
    nv = no_vlm_decisions.get(d, 0)
    wv = vlm_decisions.get(d, 0)
    delta = wv - nv
    sign = "+" if delta > 0 else ""
    print(f"| {d} | {nv} | {wv} | {sign}{delta} |")

# 개선된 케이스 상세
print("\n### VLM으로 개선된 케이스\n")
print("| 파일 | Without VLM | With VLM |")
print("|------|-------------|----------|")
vlm_changed = []
for nv, wv in zip(no_vlm_results, results):
    if nv["decision"] != wv["decision"]:
        print(f"| {nv['path']} | {nv['decision']} | {wv['decision']} |")
        vlm_changed.append({"path": nv["path"], "without_vlm": nv["decision"], "with_vlm": wv["decision"]})

# ── 8. VLM Model Comparison (2B vs 4B vs 8B) ──
print("\n\n## 8. VLM Model Comparison\n")
print("각 VLM 모델로 전체 샘플을 재평가합니다...\n")

from app.services.vlm_service import set_model, AVAILABLE_MODELS

# VLM이 호출되는 샘플만 추출 (효율)
vlm_sample_paths = [(r["path"], r["doc_type"]) for r in results if r["vlm"]]
print(f"VLM 호출 대상: {len(vlm_sample_paths)}건\n")

model_comparison = {}
for model_key in sorted(AVAILABLE_MODELS.keys()):
    print(f"--- {model_key} 모델 로딩 ---")
    set_model(model_key)

    model_results = {"decisions": Counter(), "latencies": [], "safe": 0, "safe_total": 0}
    for rel, doc_type in vlm_sample_paths:
        evaluate_fn = evaluate_id_card if doc_type == "id_card" else evaluate_bank_account
        try:
            t0 = time.time()
            resp = evaluate_fn(os.path.join(SAMPLES_DIR, rel))
            elapsed = time.time() - t0
            dec = resp.decision.value
            extracted = {f.field_name: f.value for f in resp.ocr.fields}
        except Exception as e:
            elapsed = time.time() - t0
            dec = "ERROR"
            extracted = {}

        model_results["decisions"][dec] += 1
        model_results["latencies"].append(elapsed)

        # Safe pass check
        if dec == "pass":
            gt = GT.get(rel)
            if gt:
                critical = CRITICAL_FIELDS.get(doc_type, [])
                model_results["safe_total"] += 1
                all_ok = True
                for fname in critical:
                    gt_val = gt["fields"].get(fname, "")
                    ocr_val = extracted.get(fname, "")
                    if fname == "name":
                        gt_val = gt_val.replace(" ", "")
                        ocr_val = ocr_val.replace(" ", "")
                    if not (gt_val and ocr_val and gt_val.strip() == ocr_val.strip()):
                        all_ok = False
                if all_ok:
                    model_results["safe"] += 1

        print(f"  [{model_key}] {elapsed:.1f}s {dec:16s} {rel}", flush=True)

    model_comparison[model_key] = model_results

# 비교 테이블
print("\n### Decision Distribution by Model\n")
header = "| Decision |"
sep = "|----------|"
for mk in sorted(model_comparison):
    header += f" {mk} |"
    sep += "------|"
print(header)
print(sep)
for d in ["pass", "review", "retake", "invalid_doc_type", "ERROR"]:
    row = f"| {d} |"
    for mk in sorted(model_comparison):
        row += f" {model_comparison[mk]['decisions'].get(d, 0)} |"
    print(row)

print("\n### Latency by Model\n")
print("| Model | Avg (s) | Min (s) | Max (s) |")
print("|-------|---------|---------|---------|")
for mk in sorted(model_comparison):
    lats = model_comparison[mk]["latencies"]
    if lats:
        print(f"| {mk} | {sum(lats)/len(lats):.1f} | {min(lats):.1f} | {max(lats):.1f} |")

print("\n### Safe Pass Rate by Model\n")
print("| Model | Safe | Total Pass | Rate |")
print("|-------|------|------------|------|")
for mk in sorted(model_comparison):
    mc = model_comparison[mk]
    st_val = mc["safe_total"]
    rate = mc["safe"] / st_val * 100 if st_val else 0
    print(f"| {mk} | {mc['safe']} | {st_val} | {rate:.1f}% |")

# 기본 모델로 복원
set_model("2B")

# ── Save results ──
from datetime import datetime

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
out_dir = os.path.join(os.path.dirname(__file__), "..", "reports")
os.makedirs(out_dir, exist_ok=True)

# JSON
report_json = {
    "timestamp": timestamp,
    "total_samples": total,
    "decision_distribution": dict(decisions),
    "latency": {
        "ocr_only": {"count": len(latencies["ocr_only"]), "avg": round(sum(latencies["ocr_only"]) / max(len(latencies["ocr_only"]), 1), 2), "min": round(min(latencies["ocr_only"], default=0), 2), "max": round(max(latencies["ocr_only"], default=0), 2)},
        "vlm_called": {"count": len(latencies["vlm_called"]), "avg": round(sum(latencies["vlm_called"]) / max(len(latencies["vlm_called"]), 1), 2), "min": round(min(latencies["vlm_called"], default=0), 2), "max": round(max(latencies["vlm_called"], default=0), 2)},
    },
    "vlm_call_rate": {"ocr_only": vlm_calls["ocr_only"], "vlm_called": vlm_calls["vlm_called"]},
    "safe_pass_rate": {
        "safe": safe_count,
        "total_pass": pass_total,
        "rate": round(safe_rate, 1),
        "field_accuracy": {k: {"correct": v["correct"], "total": v["total"], "accuracy": round(v["correct"] / max(v["total"], 1) * 100, 1)} for k, v in field_accuracy.items()},
        "unsafe_details": unsafe_details,
    },
    "vlm_effect": {
        "without_vlm": dict(no_vlm_decisions),
        "with_vlm": dict(vlm_decisions),
        "changed_cases": vlm_changed,
    },
    "per_sample": [{k: v for k, v in r.items() if k != "extracted"} for r in results],
    "vlm_model_comparison": {
        mk: {
            "decisions": dict(mc["decisions"]),
            "avg_latency": round(sum(mc["latencies"]) / max(len(mc["latencies"]), 1), 2),
            "safe_pass": mc["safe"],
            "safe_total": mc["safe_total"],
        } for mk, mc in model_comparison.items()
    },
}

json_path = os.path.join(out_dir, f"perf_{timestamp}.json")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(report_json, f, ensure_ascii=False, indent=2)

# Markdown (capture stdout would be complex, so regenerate key sections)
md_lines = []
md_lines.append(f"# Performance Report ({timestamp})\n")

md_lines.append("## 1. Decision Distribution\n")
md_lines.append("| Decision | Count | % |")
md_lines.append("|----------|-------|---|")
for d in ["pass", "review", "retake", "invalid_doc_type", "ERROR"]:
    cnt = decisions.get(d, 0)
    pct = cnt / total * 100 if total else 0
    md_lines.append(f"| {d} | {cnt} | {pct:.1f}% |")
md_lines.append(f"| **Total** | **{total}** | |\n")

md_lines.append("## 2. Latency\n")
md_lines.append("| Path | Count | Avg (s) | Min (s) | Max (s) |")
md_lines.append("|------|-------|---------|---------|---------|")
for tag in ["ocr_only", "vlm_called"]:
    lats = latencies[tag]
    if lats:
        md_lines.append(f"| {tag} | {len(lats)} | {sum(lats)/len(lats):.1f} | {min(lats):.1f} | {max(lats):.1f} |")
md_lines.append("")

md_lines.append("## 3. VLM Call Rate\n")
md_lines.append(f"- OCR only: {vlm_calls['ocr_only']} ({vlm_calls['ocr_only']/total*100:.1f}%)")
md_lines.append(f"- VLM called: {vlm_calls['vlm_called']} ({vlm_calls['vlm_called']/total*100:.1f}%)\n")

md_lines.append("## 4. Failure Modes (top 10)\n")
md_lines.append("| Mode | Count |")
md_lines.append("|------|-------|")
for mode, files in sorted(failure_modes.items(), key=lambda x: -len(x[1]))[:10]:
    md_lines.append(f"| {mode[:80]} | {len(files)} |")
md_lines.append("")

md_lines.append("## 5. Per-folder Summary\n")
md_lines.append("| Folder | pass | review | retake | invalid | Avg Latency |")
md_lines.append("|--------|------|--------|--------|---------|-------------|")
for folder in sorted(folder_data):
    items = folder_data[folder]
    dc = Counter(r["decision"] for r in items)
    avg_lat = sum(r["latency"] for r in items) / len(items)
    md_lines.append(f"| {folder} | {dc.get('pass',0)} | {dc.get('review',0)} | {dc.get('retake',0)} | {dc.get('invalid_doc_type',0)} | {avg_lat:.1f}s |")
md_lines.append("")

md_lines.append("## 6. Safe Pass Rate\n")
md_lines.append(f"**{safe_count}/{pass_total} ({safe_rate:.1f}%)**\n")
md_lines.append("| Field | Correct | Total | Accuracy |")
md_lines.append("|-------|---------|-------|----------|")
for fname in sorted(field_accuracy):
    fa = field_accuracy[fname]
    acc = fa["correct"] / fa["total"] * 100 if fa["total"] else 0
    md_lines.append(f"| {fname} | {fa['correct']} | {fa['total']} | {acc:.1f}% |")
if unsafe_details:
    md_lines.append("\n### Unsafe Pass\n")
    for d in unsafe_details:
        md_lines.append(f"- {d}")
md_lines.append("")

md_lines.append("## 7. VLM Effect\n")
md_lines.append("| Decision | Without VLM | With VLM | Delta |")
md_lines.append("|----------|-------------|----------|-------|")
for d in ["pass", "review", "retake", "invalid_doc_type"]:
    nv = no_vlm_decisions.get(d, 0)
    wv = vlm_decisions.get(d, 0)
    delta = wv - nv
    sign = "+" if delta > 0 else ""
    md_lines.append(f"| {d} | {nv} | {wv} | {sign}{delta} |")
if vlm_changed:
    md_lines.append("\n### Changed Cases\n")
    md_lines.append("| File | Without VLM | With VLM |")
    md_lines.append("|------|-------------|----------|")
    for c in vlm_changed:
        md_lines.append(f"| {c['path']} | {c['without_vlm']} | {c['with_vlm']} |")

md_lines.append("\n## 8. VLM Model Comparison\n")
md_lines.append(f"VLM 호출 대상: {len(vlm_sample_paths)}건\n")
header = "| Decision |"
sep = "|----------|"
for mk in sorted(model_comparison):
    header += f" {mk} |"
    sep += "------|"
md_lines.append(header)
md_lines.append(sep)
for d in ["pass", "review", "retake", "invalid_doc_type", "ERROR"]:
    row = f"| {d} |"
    for mk in sorted(model_comparison):
        row += f" {model_comparison[mk]['decisions'].get(d, 0)} |"
    md_lines.append(row)

md_lines.append("\n### Latency\n")
md_lines.append("| Model | Avg (s) | Min (s) | Max (s) |")
md_lines.append("|-------|---------|---------|---------|")
for mk in sorted(model_comparison):
    lats = model_comparison[mk]["latencies"]
    if lats:
        md_lines.append(f"| {mk} | {sum(lats)/len(lats):.1f} | {min(lats):.1f} | {max(lats):.1f} |")

md_lines.append("\n### Safe Pass Rate\n")
md_lines.append("| Model | Safe | Total Pass | Rate |")
md_lines.append("|-------|------|------------|------|")
for mk in sorted(model_comparison):
    mc = model_comparison[mk]
    st_val = mc["safe_total"]
    rate = mc["safe"] / st_val * 100 if st_val else 0
    md_lines.append(f"| {mk} | {mc['safe']} | {st_val} | {rate:.1f}% |")

md_path = os.path.join(out_dir, f"perf_{timestamp}.md")
with open(md_path, "w", encoding="utf-8") as f:
    f.write("\n".join(md_lines))

print(f"\n\n✅ Reports saved:")
print(f"  JSON: {json_path}")
print(f"  MD:   {md_path}")
