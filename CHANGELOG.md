# Changelog

## Unreleased

- Added the typical-data reference ("数据特征参考") card to every experiment page: each published experiment ships `data_reference.json` next to its config with 3-6 measured quantities, handwriting-precision example values and expected patterns, rendered where the blank record sheet is downloaded.
- The reference values are re-derived from each experiment's own formulas and standard constants by `backend/tests/test_data_reference.py` (Malus law, air/water sound speed, light speed, Cu50 slope, solar-cell fill factor and charge cutoff, GMR single-branch sensitivity, NMR gyromagnetic ratio, viscosity range, surface tension from 0.07275 N/m, Michelson wavelength, Planck constant, Franck-Hertz peak spacing).
- Reference data is informational only: the card has no inputs and never feeds the calculation chain or the record sheet.

- Added the offline consent-first OCR dataset pipeline (`backend/ocr_dataset`): calibrated per-experiment record-sheet layouts, template registration with orientation rejection, OpenCV grid fallback, crop quality gates, deterministic sample IDs, contact-sheet preview and a dry-run CLI.
- Calibrated `layouts/<experiment_id>.json` for all 12 public experiments (517 page-1 handwriting cells) from the record sheets this repository renders.
- Collection commits now accept and preserve numeric strings, so a confirmed `"22.090"` keeps its trailing zero instead of becoming `22.09`.

## 2.0.0-beta.1 - 2026-09-16

- Added a shared experiment schema with canonical backend validation and warning-first expected ranges.
- Added the merged `photoelectric-franck-hertz` catalogue entry while preserving legacy IDs and API routes.
- Added an OCR provider boundary (`RapidOCRProvider` with optional `PaddleOCRProvider`) and verified cell feedback storage.
- Added anonymous analytics, OCR correction metrics, and a consent-gated dataset export script.
- Kept report generation, plotting, record sheets, and the existing polarization/sound-light workflows compatible.
- Added a persistent public-beta notice with a direct GitHub feedback link.

Known boundary: current OCR and calculation verification uses unit tests and synthetic fixtures. A labeled real handwritten dataset is still required before claiming production handwriting accuracy.
