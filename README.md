# Quotation Image Automation System

Automated insertion of product images into quotation PDFs using PyMuPDF.

> 📌 **คู่มือสถานะโครงการและการย้ายไปทำต่อใน Environment ใหม่:** ดูได้ที่ [PROGRESS.md](PROGRESS.md)

## Phase 1 — PDF Engine Proof of Concept

Phase 1 provides the core PDF engine, matching system, boundary detector, and image renderer without requiring databases or external microservices.

### Features
- **PyMuPDF Selectable-Text Extraction**: Native coordinate and text extraction without slow or unreliable OCR.
- **Dynamic Item Row Boundaries**: Dynamically detects the vertical span `[y0, y1]` of each quotation item based on sequential row markers and footer boundaries.
- **5-Tier Product Matching**: Strict matching priority hierarchy:
  1. Exact SKU (`confidence = 1.0`)
  2. Exact Winspeed (`confidence = 0.95`)
  3. Normalized SKU (`confidence = 0.90`)
  4. Model Match (`confidence = 0.80`, or `needs_review` if multiple candidates exist)
  5. Missing / Manual Review (`confidence = 0.0`)
- **Aspect-Ratio Preserving Image Insertion**: Fits images inside the `DESCRIPTION` column with zero stretching and strict column clearance preventing overlap with `QTY`, `PRICE`, or `NET PRICE`.
- **Fault-Tolerant HTTP Retrieval**: Missing images or network timeouts log warnings and mark items as `missing` without failing quotation generation.

---

### Running Tests

Run all unit and integration tests:

```bash
python -m unittest discover -s apps/api/tests -p "test_*.py"
```

---

### Running the Phase 1 CLI

Process any quotation PDF from the command line:

```bash
# Set PYTHONPATH to apps/api
$env:PYTHONPATH="apps/api"   # On Windows PowerShell
# export PYTHONPATH="apps/api" # On Linux / macOS

python -m app.cli <path_to_quotation.pdf> -p <path_to_products.json> -o <output_path.pdf>
```

Example:

```bash
$env:PYTHONPATH="apps/api"; python -m app.cli sample_quotation.pdf -p sample_products.json -o output.pdf
```
