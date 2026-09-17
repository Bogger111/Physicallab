# Optional record-sheet collection

This directory is the local implementation of the optional, consent-first
record-sheet collection interface. The feature is disabled by default. Enable
it with `ENABLE_DATA_COLLECTION=true` and optionally set
`PHYSICSLAB_COLLECTION_ROOT` to a persistent directory.

Runtime files are intentionally ignored by Git:

- `raw/<session_id>.jpg`: the user-provided full record-sheet image, decoded
  and re-encoded as JPEG to remove EXIF and embedded metadata;
- `metadata/<session_id>.json`: consent, experiment/template identifiers,
  timestamps, revision number, and confirmed values keyed by stable schema IDs.

The UI must ask for explicit consent before upload. Users are told to crop or
redact names, student IDs, phone/WeChat details, faces, identity documents, and
other personal information before contributing. Declining does not remove any
experiment, calculation, validation, OCR, or report function.

Only a successful report download triggers confirmed field labels. Repeated
report generation updates the same session and increments its revision. The
online API does not crop cells, perform training, identify users, or store
request IP addresses, headers, browser fingerprints, or account data. Offline
numeric-cell segmentation and review live in `backend/ocr_dataset`; they do not
change this API or copy full source pages into dataset output.

Local disk in a Cloud Run instance is ephemeral. A production deployment that
enables this feature must supply a persistent `CollectionStorage`
implementation before treating collected files as durable.
