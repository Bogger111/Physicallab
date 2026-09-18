# Consent-first OCR dataset builder

Offline pipeline that turns final, explicitly consented collection sessions into
single-value training crops for the CRNN + CTC recogniser. It never changes
session metadata, never copies a full source page into the dataset, and never
guesses which field a piece of handwriting belongs to.

```
collection store ──▶ collector ──▶ preprocess ──▶ registration ──▶ segment ──▶ quality ──▶ exporter
 (consent+commit)     (latest      (EXIF,        (template line     (calibrated (charset,   (PNG, CSV,
                       revision)    grayscale,     lattice +          ROI or      blank/     manifest,
                                    rectified      orientation)       OpenCV      size/ink)  contact
                                    page)                             fallback)              sheet)
```

## Usage

```bash
python -m backend.ocr_dataset.build --output data/ocr_dataset --dry-run
python -m backend.ocr_dataset.build --output data/ocr_dataset --overwrite
python -m backend.ocr_dataset.build --output data/ocr_dataset --experiment sound-light
python -m backend.ocr_dataset.build --output data/ocr_dataset --session-id SESSION_UUID
```

`--collection-root` reads a non-default collection store, `--layouts-dir` uses
uncommitted layouts, `--denoise` enables NL-means denoising, `--charset-config`
overrides the label charset. `--dry-run` performs every step in memory, prints
counts and reject reasons, and writes nothing.

Re-calibrating the layouts after a record-sheet change:

```bash
python -m backend.ocr_dataset.calibrate --all --write --overlay artifacts/_calib
```

## PhysLab_OCR export (template-driven, `image,text`)

The training repository `Bogger111/PhysLab_OCR` reads exactly two things:

```
data/images/*.png
data/labels.csv          # header: image,text
```

`ocr_dataset.builder` produces that shape directly from a confirmed session, and
`backend/ocr_layouts/<experiment>.json` holds the per-experiment template (which
cell belongs to which stable field id):

```bash
python -m backend.ocr_dataset.builder --session-id SESSION_UUID --output <dir>
python -m backend.ocr_dataset.builder --session-id SESSION_UUID --dry-run
python -m backend.ocr_dataset.templates --check        # template/calibration drift
python -m backend.ocr_dataset.templates --write        # regenerate from calibration
```

Templates are generated from the calibrated layouts, so a field id can never
point at the wrong cell.  Everything else the run produces (`samples.csv`,
`rejected.csv`, `manifest.json`) is provenance and stays out of `labels.csv`:

* `image` is always a bare filename — the OCR loader does `Path(image_dir) / row["image"]`;
* every label must be encodable with the OCR charset (`0123456789.`) or its
  `encode()` raises, so `-0.5`, `22.09 mV` and `1.2e-3` are rejected, never clipped;
* crops keep the original aspect ratio and a single value each: resizing to
  160x80 is the OCR dataset transform's job.

## Input contract

Only sessions that satisfy all of the following are read:

| Condition | Reject reason when violated |
|---|---|
| `consent == true` | `consent_not_explicit` |
| `status == "confirmed"` (report downloaded) | `not_finally_committed` |
| `revision >= 1`, newest revision per session wins | `invalid_revision` |
| no identity keys in the metadata, `deidentified != false` | `personal_information_not_removed` |
| `image_path == raw/<session_id>.jpg` and the file exists | `invalid_source_image_reference`, `missing_source_image` |
| every field ID validates against the current experiment config | `invalid_field_mapping` |

Labels keep the committed string: `"22.090"` stays `"22.090"`. Legacy numeric
values are stringified without reformatting.

## Layout contract (`layouts/<experiment_id>.json`)

The record sheet this repository renders *is* the layout template. Calibration
draws the sheet with reportlab, records the rectangle of every table cell
reportlab paints, maps those rectangles onto stable field IDs from the same
config that produces the confirmed values, and freezes the result:

```json
{
  "schema_version": "2.0",
  "experiment_id": "multimeter",
  "reference_size": [1600, 2263],
  "source": {"kind": "record_sheet_pdf", "page": 1,
             "raster_match_ratio": 0.97, "raster_offset_px": [-14, 0]},
  "fields": {
    "voltage.rows.row_01.measured": {"x1": 0.51, "y1": 0.09, "x2": 0.95, "y2": 0.11,
                                     "page": 1, "confidence": 0.9}
  },
  "anchors": [[0.0675, 0.0703, 0.9531, 0.4255]],
  "lattice": {"x": [0.0675, 0.51, 0.953], "y": [0.0703, 0.0997]},
  "tables": [{"method_id": "voltage", "section": "rows", "row_count": 11,
              "columns": ["set", "measured"]}]
}
```

- `reference_size` is `[width, height]` of the canonical table coordinate
  system: A4 portrait (210 x 297 mm) at ~193 dpi. The paper ratio must match, or
  perspective correction would skew every relative coordinate.
- `fields` — one entry per handwriting cell on **page 1**, keyed by the stable
  field ID produced by `app.data_collection.valid_stable_field_id`. Cells the
  blank sheet prints itself (序号, 设值, cos²θ, defaults) are deliberately absent:
  they are not handwriting targets.
- `anchors` — page-1 table frames, drawn by the `--overlay` review image.
- `lattice` — every printed line of page 1; the registration reference.
- `tables` — coarse table signatures, used only by the OpenCV fallback.
- `source.raster_match_ratio` — fraction of captured cell edges that coincide
  with lines really painted on the rasterised page. Calibration refuses to write
  a layout below `0.75`.

`Fields past page 1 are unreachable today`: one collection session stores a
single image, so a field printed on page 2+ can never be traced back to the
uploaded page. Those cells are counted as `unmapped_cells` during calibration
and rejected as `missing_field_mapping` at build time. Coverage per experiment
is reported by `calibrate --all`.

## Segmentation

1. **Registration check first.** `segment.register_page` extracts the printed
   grid lines (unbiased ink-projection profiles) and compares them with the
   frozen `lattice`. The page is trusted only when

   - recall ≥ 0.8 — every detected line is explained by the template (a cropped,
     rescaled, shifted or unrelated page leaves lines that are not), **and**
   - precision ≥ 0.3 — a usable share of the template lines is visible, **and**
   - the upright lattice explains the grid at least 0.05 better than the 180°
     rotated one (an upside-down page is explained better by the mirrored
     lattice; a page the two cannot be told apart on is rejected as
     `page_orientation_ambiguous`).

   Failing any of these rejects every field of the session — `grid_mismatch`,
   `page_upside_down`, `no_printed_grid_found`, `layout_not_calibrated`.
2. **Calibrated ROI crop** with 3.5 % padding used as context for removing the
   printed rules (the padding band is where the rules live, so the exported PNG
   stays inside the cell). Nothing is resized here: resize/pad belongs to the
   PyTorch dataset transform.
3. **OpenCV fallback** (`opencv_grid_fallback`) for experiments without
   calibrated ROIs: adaptive threshold, horizontal/vertical line extraction,
   morphology, contour detection, cell bounding boxes. A signature is accepted
   only when the detected grid matches it uniquely — otherwise
   `missing_field_mapping` / `ambiguous_field_mapping`. No deep-learning
   segmentation is used.
4. **Ink tightening.** The crop is shrunk onto the handwritten value with a
   margin (8 % horizontally, 15 % vertically, min 2 px), after dropping speckle
   left by rule removal and ignoring the outermost pixel ring. A mark far from
   the rest of the ink is reported as `detached_ink_mark` instead of being
   silently merged or trimmed. Grayscale is preserved; no binarisation.

## Quality gate (`quality.py`)

Reject: `empty_label`, `illegal_charset`, `missing_crop`, `extremely_small_crop`
(< 12 px or < 240 px²), `suspiciously_dark_crop`, `blank_or_white_crop`.
Review (kept out of `labels.csv`, listed in `rejected.csv`): `ink_touches_roi_border`,
`low_segmentation_confidence`, `detached_ink_mark`.

The charset comes from `charset.json` (`numeric-v1`: `0123456789.`) and is never
hardcoded in segmentation.

## Output

```
ocr_dataset/
├── images/<session>_<field>.png     # one grayscale value, no full pages
├── labels.csv                       # image,text,experiment_id,field_id,session_id,
│                                    # source_image,revision,segmentation_method,quality_score
├── rejected.csv                     # sample_id,experiment_id,field_id,session_id,
│                                    # source_image,revision,disposition,reason
├── manifest.json                    # charset, counts, segmentation mix, reasons, privacy contract
└── preview/contact_sheet.png        # crop + ground truth + experiment/field, 3 per row
```

`--overwrite` replaces a previous dataset; a non-empty output directory without
the flag is an error. Sample IDs are `sha256(session_id ␟ field_id ␟ revision)`,
so re-running is idempotent and every crop is traceable to its revision.

## Privacy

Names, student IDs, contact details and complete uncropped pages are never
copied into the dataset: only numeric crops and the minimal provenance columns
above. `manifest.json` states the contract explicitly
(`contains_full_source_pages: false`).

## Tests

```bash
cd backend && python -m pytest ocr_dataset/tests -q
```

Tests render the real record sheets and use them as synthetic uploads (a photo
on a desk, an upright scan, an upside-down page, a cropped page, a shifted page,
a padded frame, a blank page), plus synthetic handwriting drawn into calibrated
cells. No real user data is involved. They cover label-string preservation
(`"22.090"` never becomes `"22.09"`), the coordinate convention against the
rendered PDF text, ROI/grid agreement, template and perspective-corrected crops,
rejection of unregistered pages, deterministic sample IDs, revision handling and
contact-sheet generation.

The older `scripts/export_ocr_dataset.py` remains for the legacy
`manifest.csv` + full-image export; it does not crop cells and is unrelated to
this pipeline.
