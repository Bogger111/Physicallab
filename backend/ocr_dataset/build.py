"""CLI for building consented numeric-cell OCR training datasets.

Usage:
    python -m backend.ocr_dataset.build --output data/ocr_dataset
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.data_collection import collection_root

from .collector import CollectionReject, collect_sessions
from .exporter import (
    AcceptedSample,
    BuildResult,
    RejectedSample,
    deterministic_sample_id,
    export_dataset,
)
from .preprocess import preprocess_page
from .quality import evaluate_crop, load_charset, validate_label
from .segment import load_layout, segmenter_for


def _collector_reject(item: CollectionReject) -> RejectedSample:
    sample_id = (
        deterministic_sample_id(item.session_id, item.field_id or "__session__", item.revision or 0)
        if item.session_id else ""
    )
    return RejectedSample(
        sample_id, item.experiment_id, item.field_id, item.session_id,
        item.source_image, item.revision, item.disposition, (item.reason,),
    )


def build_dataset(
    source_root: Path,
    *,
    experiment_id: str | None = None,
    session_id: str | None = None,
    layouts_dir: Path | None = None,
    charset_path: Path | None = None,
    denoise: bool = False,
) -> tuple[BuildResult, str, str]:
    charset, charset_version = load_charset(charset_path)
    sessions, collection_rejects = collect_sessions(
        source_root, experiment_id=experiment_id, session_id=session_id,
    )
    result = BuildResult(
        rejected=[_collector_reject(item) for item in collection_rejects],
        sessions_seen=len(sessions),
    )
    seen_sample_ids: set[str] = set()
    for session in sessions:
        try:
            layout = load_layout(session.experiment_id, layouts_dir)
            reference_size = tuple(layout["reference_size"])
            page = preprocess_page(session.source_image, reference_size, denoise=denoise)
            segmenter = segmenter_for(page, layout)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            for field_id in session.fields:
                sample_id = deterministic_sample_id(session.session_id, field_id, session.revision)
                result.rejected.append(RejectedSample(
                    sample_id, session.experiment_id, field_id, session.session_id,
                    session.source_image_ref, session.revision, "reject",
                    (f"preprocess_failed:{type(exc).__name__}",),
                ))
            continue
        if not segmenter.registration.registered:
            # The upload is not the page this layout was calibrated against, so
            # its coordinates mean nothing: reject instead of guessing.
            result.registration_failures += 1
        for field_id, text in sorted(session.fields.items()):
            sample_id = deterministic_sample_id(session.session_id, field_id, session.revision)
            if sample_id in seen_sample_ids:
                result.rejected.append(RejectedSample(
                    sample_id, session.experiment_id, field_id, session.session_id,
                    session.source_image_ref, session.revision, "reject", ("duplicate_sample",),
                ))
                continue
            seen_sample_ids.add(sample_id)
            label_errors = validate_label(text, charset)
            if label_errors:
                result.rejected.append(RejectedSample(
                    sample_id, session.experiment_id, field_id, session.session_id,
                    session.source_image_ref, session.revision, "reject", label_errors,
                ))
                continue
            crop = segmenter.crop(field_id)
            if crop.image is None:
                result.rejected.append(RejectedSample(
                    sample_id, session.experiment_id, field_id, session.session_id,
                    session.source_image_ref, session.revision, "reject",
                    (crop.reason or "segmentation_failed",),
                ))
                continue
            decision = evaluate_crop(
                crop.image, label=text, charset=charset,
                segmentation_confidence=crop.confidence,
                touches_roi_border=crop.touches_roi_border,
                segmentation_notes=crop.notes,
            )
            if decision.disposition != "accept":
                result.rejected.append(RejectedSample(
                    sample_id, session.experiment_id, field_id, session.session_id,
                    session.source_image_ref, session.revision, decision.disposition,
                    decision.reasons,
                ))
                continue
            result.accepted.append(AcceptedSample(
                sample_id, crop.image, text, session.experiment_id, field_id,
                session.session_id, session.source_image_ref, session.revision,
                crop.method, decision.score,
            ))
    return result, charset, charset_version


def _summary(result: BuildResult, *, dry_run: bool, output: Path) -> dict:
    return {
        "dry_run": dry_run,
        "output": str(output),
        "sessions": result.sessions_seen,
        "exportable_samples": len(result.accepted),
        "rejected_or_review": len(result.rejected),
        "reasons": result.reason_counts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/ocr_dataset"))
    parser.add_argument("--collection-root", type=Path, default=None)
    parser.add_argument("--experiment", dest="experiment_id")
    parser.add_argument("--session-id")
    parser.add_argument("--layouts-dir", type=Path, default=None)
    parser.add_argument("--charset-config", type=Path, default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--denoise", action="store_true")
    args = parser.parse_args(argv)
    source = args.collection_root or collection_root()
    result, charset, charset_version = build_dataset(
        source, experiment_id=args.experiment_id, session_id=args.session_id,
        layouts_dir=args.layouts_dir, charset_path=args.charset_config,
        denoise=args.denoise,
    )
    if not args.dry_run:
        export_dataset(
            result, args.output, charset=charset, charset_version=charset_version,
            overwrite=args.overwrite,
        )
    print(json.dumps(_summary(result, dry_run=args.dry_run, output=args.output),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
