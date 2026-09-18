# Optional record-sheet collection

This directory is the local implementation of the optional, consent-first
record-sheet collection interface. The feature is disabled by default. Enable
it with `ENABLE_DATA_COLLECTION=true` and optionally set
`PHYSICSLAB_COLLECTION_ROOT` to a persistent directory.

## Development switch

The feature is off unless a switch turns it on, and the same switch drives local
development and production:

```bash
# backend/.env.local  (git-ignored, read at startup by app.dev_env)
ENABLE_DATA_COLLECTION=true
# optional: keep collected data outside the repository
# PHYSICSLAB_COLLECTION_ROOT=D:/physicslab-private/collection
```

`app.dev_env.load_local_env()` reads `backend/.env.local` then `backend/.env` and
only fills keys that are **not already set**, so a real deployment (Cloud Run env
vars, exported shell variables, CI) always wins and a checked-out file can never
change production behavior.  `backend/.env.local` is listed in `.gitignore`.

Storage stays behind `CollectionStorage`; the implementation in use today is
`LocalFileStorage` (files under `backend/data_collection/`, or
`PHYSICSLAB_COLLECTION_ROOT`).  Nothing else in the code base knows where the
bytes live, so a bucket-backed implementation replaces `local_storage()` only.

Runtime files are intentionally ignored by Git, and the layout mirrors the
production private-bucket prefix one to one:

- `sessions/<session_id>/raw.jpg`: the user-provided full record-sheet image,
  decoded and re-encoded as JPEG to remove EXIF and embedded metadata;
- `sessions/<session_id>/metadata.json`: consent, experiment/template
  identifiers, timestamps, revision number, and confirmed values keyed by stable
  schema IDs;
- `datasets/<export>/`: derived output only (`images/`, `labels.csv`).  Source
  pages are never copied into it, because numeric crops are produced from the
  private image at build time.

The UI must ask for explicit consent before upload. Users are told to crop or
redact names, student IDs, phone/WeChat details, faces, identity documents, and
other personal information before contributing. Declining does not remove any
experiment, calculation, validation, OCR, or report function.

Only a successful report download triggers confirmed field labels. Repeated
report generation updates the same session and increments its revision.

`POST /api/data-collection/sessions/{id}/build-ocr` turns one confirmed session
into a `PhysLab_OCR` compatible dataset (see `backend/ocr_dataset/builder.py`):
template-driven OpenCV cropping, a quality gate, and only numeric crops in the
output.  It is gated by the same `ENABLE_DATA_COLLECTION` flag. The
online API does not crop cells, perform training, identify users, or store
request IP addresses, headers, browser fingerprints, or account data. Offline
numeric-cell segmentation and review live in `backend/ocr_dataset`; they do not
change this API or copy full source pages into dataset output.

## Statistics (developer surface)

`GET /api/data-collection/stats` returns `total_sessions`, `confirmed_sessions`,
`samples_created` and a per-experiment breakdown.  It reads only session
metadata and the dataset index (`datasets/<export>/samples.csv`): images are
never scanned or opened.

Access is closed by default:

| Configuration | Result |
|---|---|
| `PHYSICSLAB_ADMIN_KEY` set, header `X-Admin-Key` matches | 200 (constant-time compare) |
| `PHYSICSLAB_ADMIN_KEY` set, header missing or wrong | 404 |
| no admin key, `PHYSICSLAB_DEV_MODE=true` | 200 (local development only) |
| neither | 404 — the endpoint is not advertised |

The matching page is `/dev/data-collection` in the frontend, rendered only when
`NEXT_PUBLIC_PHYSICSLAB_DEV_MODE=true` is part of the build, marked `noindex` and
absent from the navigation.

Local disk in a Cloud Run instance is ephemeral. A production deployment that
enables this feature must supply a persistent `CollectionStorage`
implementation before treating collected files as durable.
