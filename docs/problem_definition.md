# Problem Definition

## Overview

In financial services, users are required to upload documents such as ID cards or bank account verification forms. However, these inputs are often imperfect due to real-world conditions such as blur, cropping, glare, or partial occlusion.

Under such conditions, relying solely on OCR outputs is insufficient to make reliable decisions. OCR may fail to extract critical fields or produce low-confidence and inconsistent results.

This project formulates document validation as a **decision-making problem under imperfect inputs**, where the system must determine the appropriate action based on both image quality and extracted information.

---

## Objective

Given a document image, the system determines one of the following actions:

- **pass**: the document is valid and can be automatically accepted  
- **retake**: the input quality is insufficient and the user must re-upload  
- **review**: the input is usable, but the system lacks confidence and requires human verification  

---

## Key Challenge

The main challenge lies in distinguishing between:

- **input quality issues** (e.g., blur, glare, crop) → should trigger `retake`  
- **semantic uncertainty** (e.g., ambiguous OCR results, partial field mismatch) → should trigger `review`  

This distinction is critical for balancing user experience and operational cost:
- Overusing `retake` degrades UX  
- Overusing `review` increases manual verification cost  

---

## Scope

### Input Types

- One type of **ID document image** (e.g., ID card, driver's license)
- One type of **bank-related document** containing account information

### Input Conditions

The system must handle imperfect inputs including:
- blur
- crop (partial document)
- glare / reflection
- partial occlusion

---

## Out of Scope

- Full OCR model training or fine-tuning
- Multi-document or multi-page processing
- Advanced fraud detection (e.g., forgery detection)
- Face recognition or biometric verification

---

## Approach (MVP)

The system will:
1. Extract text using an OCR engine
2. Evaluate image quality (e.g., blur, crop)
3. Apply rule-based validation on extracted fields
4. Combine signals to produce a final decision: `pass`, `retake`, or `review`

---

## Expected Outcome

A lightweight, end-to-end prototype that demonstrates:

- Decision-making under imperfect visual inputs
- Integration of OCR + rule-based validation
- Clear separation between quality failure and uncertainty-driven review