# Decision Rules

## Overview

This document defines how the system determines the final decision:

- `pass`
- `retake`
- `review`

The decision is based on a combination of:

1. **Image quality signals**
2. **Field presence and extraction results**
3. **Validation of extracted information**

---

## Decision Philosophy

The system distinguishes between two fundamentally different failure types:

### 1. Input Quality Failure → `retake`

The input image is physically insufficient for reliable interpretation.

Examples:
- blur
- glare
- crop (missing regions)
- severe occlusion

→ The correct action is to request a new upload.

---

### 2. Uncertainty / Ambiguity → `review`

The image is usable, but the system cannot make a confident decision.

Examples:
- OCR extracted fields with low confidence
- partial mismatch in expected format
- ambiguous document type

→ The correct action is to defer to human verification.

---

## Decision Categories

### PASS

The document is automatically accepted.

#### Conditions

- Image quality is acceptable
- Required fields are present
- Field values pass basic validation rules
- No major inconsistencies detected

---

### RETAKE

The user must re-upload the document.

#### Trigger Conditions (Quality Failure)

Any of the following:

- Image is too blurry (below threshold)
- Critical regions are cropped or missing
- Strong glare or reflection obscures text
- Resolution is too low to read text

#### Key Principle

> If a human cannot reliably read the document, the system should not attempt to interpret it.

---

### REVIEW

The document is sent for manual verification.

#### Trigger Conditions (Uncertainty)

- Required fields partially missing but image quality is acceptable
- OCR output is inconsistent or low confidence
- Field format validation fails (but not clearly invalid)
- Document type classification is ambiguous

#### Key Principle

> If the input is readable but the system lacks confidence, escalate to human review.

---

## Rule Structure

The system evaluates in the following order:

### Step 1. Image Quality Check

Evaluate:
- blur score
- glare detection
- crop detection
if quality is severely degraded:
→ retake 
 

### Step 2. Required Field Check

Evaluate:
- name_present
- id_number_present (or account_number_present)


if required fields are missing:
→ review

 

### Step 3. Field Validation

Evaluate:
- format validity (e.g., ID number pattern)
- basic consistency checks


if format is clearly invalid:
→ review
 
### Step 4. Final Decision


if quality OK
and required fields present
and validation passed:
→ pass
else:
→ review
 

## Summary Table

| Condition                          | Decision  |
|-----------------------------------|-----------|
| Severe blur / glare / crop        | retake    |
| Missing required fields           | review    |
| Low OCR confidence                | review    |
| Format validation failure         | review    |
| All checks passed                 | pass      |

---

## Notes

- `retake` is strictly for **input quality issues**
- `review` is strictly for **decision uncertainty**
- These two must not be mixed

---

## Future Extensions

- Confidence scoring for OCR outputs
- Learned decision model replacing rule-based logic
- Integration with VLM for semantic validation
- Adaptive thresholds based on data distribution