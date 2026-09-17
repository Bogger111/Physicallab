# Public experiment regression fixtures

This directory is the offline regression corpus for the 12 experiments shown in
the PhysKiller catalogue. Every experiment has three cases:

- `typical.json`: complete synthetic data, materialized from the repository's
  pre-existing calculation and report fixtures and expanded to the current
  configured row counts.
- `boundary.json`: inherits `typical.json` and identifies values at a configured
  or algorithmic boundary. Where the lecture material does not establish a
  defensible scientific range, the file says that the coverage is structural.
- `invalid.json`: inherits `typical.json` and removes one required measurement.

Every file carries the same provenance fields:

```json
{
  "experiment_id": "...",
  "fixture_type": "typical | boundary | invalid",
  "source": "synthetic | structure-derived | real",
  "verified": false,
  "notes": "..."
}
```

`verified` remains false for the current corpus because no complete real
laboratory record has passed human image-to-label review.

`boundary.json` and `invalid.json` use a small checked-in patch format so the
complete data is not duplicated. A patch contains `op: replace`, a list-valued
`path`, and a JSON `value`. The loader lives in
`test_public_experiment_usability.py`.

These fixtures do not contain student data and do not establish correctness for
complete real laboratory measurements. They run without external services or
network access. Lab-confirmed range data should replace entries explicitly
marked `structure-derived` when it becomes available.
