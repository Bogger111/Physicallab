# Changelog

## Unreleased

- Enabled the collection loop for local development: `backend/.env.local` (`ENABLE_DATA_COLLECTION=true`, git-ignored) is read at startup by the dependency-free `app.dev_env`, where real environment variables always win so production config is untouched.
- Renamed the filesystem storage implementation to `LocalFileStorage` (the documented default behind `CollectionStorage`; `LocalCollectionStorage` remains as an alias).
- The contribution panel now shows the saved `session_id` and 「记录已保存，可用于后续优化实验数据识别能力。」 after a successful upload.
- Verified the closed loop locally: upload → `sessions/<uuid>/{raw.jpg,metadata.json}` → commit → `POST .../build-ocr` → `datasets/ocr_export/{images/*.png, labels.csv}` → copied into `PhysLab_OCR/data/`, where the unmodified `train.py` trained to `Loss 0.1013` with `Pred: 26.59` matching the label.

- Added the `PhysLab` → `PhysLab_OCR` dataset pipeline: `POST /api/data-collection/sessions/{id}/build-ocr` turns one confirmed session into `images/*.png` + `labels.csv` (`image,text` only), with `samples.csv`, `rejected.csv` and `manifest.json` as separate provenance.
- Added `backend/ocr_layouts/<experiment>.json` templates (field id → record-sheet cell) generated from the calibrated layouts, plus `ocr_dataset/templates.py` drift checks so a template can never disagree with its calibration.
- Collection storage moved to `sessions/<uuid>/raw.jpg` + `metadata.json` (mirroring the production private-bucket prefix), with `CollectionStorage.load_session()` keeping the interface storage-agnostic; `datasets/<export>/` holds derived output only.
- Fixed three crop-quality defects found while building this: wide cells no longer collapse to "blank" (printed-rule residue no longer inflates the ink area floor or the stroke scale), a vertical rule ghost no longer stretches a crop across empty paper, and printed-rule hairlines are whitened out of the exported crop.
- Fixed a 500 in the export path when a session produced zero samples (empty `samples.csv` write).
- The legacy `scripts/export_ocr_dataset.py` collection export now accepts confirmed numeric *strings* (it silently dropped `"22.090"`) and no longer copies full source pages out of private storage; it references the private path instead.
- The consent-first collection API, all experiment calculations, and the OCR feedback path are unchanged.

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
