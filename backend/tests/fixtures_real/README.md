# Real-world experiment fixtures

This directory is reserved for future real laboratory records. It intentionally
contains no fabricated "real" samples.

Before a sample can enter this directory it must:

- be anonymized;
- contain no name, student ID, phone number, messaging account, face, identity
  document, or other personal identifier;
- identify the experiment and template version unambiguously;
- include human-confirmed ground truth values with stable schema field IDs;
- record the source date and provenance;
- record whether the contributor consented to model-training use;
- document any image masking or redaction already applied.

Real samples must use metadata that distinguishes `source: real` from
`synthetic` and `structure-derived`, and must not set `verified: true` until a
human reviewer has checked the image-to-label correspondence.

Do not commit raw, unreviewed uploads or personal data to Git.

