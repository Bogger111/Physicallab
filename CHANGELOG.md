# Changelog

## 2.0.0-beta.1 - 2026-09-16

- Added a shared experiment schema with canonical backend validation and warning-first expected ranges.
- Added the merged `photoelectric-franck-hertz` catalogue entry while preserving legacy IDs and API routes.
- Added an OCR provider boundary (`RapidOCRProvider` with optional `PaddleOCRProvider`) and verified cell feedback storage.
- Added anonymous analytics, OCR correction metrics, and a consent-gated dataset export script.
- Kept report generation, plotting, record sheets, and the existing polarization/sound-light workflows compatible.
- Added a persistent public-beta notice with a direct GitHub feedback link.

Known boundary: current OCR and calculation verification uses unit tests and synthetic fixtures. A labeled real handwritten dataset is still required before claiming production handwriting accuracy.
