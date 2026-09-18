"""Backend package marker: allows `python -m backend.ocr_dataset.export` from the repository root.

Runtime code imports its siblings as top-level modules (`app.*`, `experiments.*`,
`ocr_dataset.*`) with `backend/` on `sys.path`; this marker only makes the
repository-root invocation form work as documented.
"""
