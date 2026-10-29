# BSides Challenge Author Notes

This repo now has a dedicated multi-stage challenge path separate from the original employee portal.

## Public Flow

1. `/incident`
   - Players inspect staged dump photos and reconstruct the controlled event phone number.
   - Staged photos live in `public/images/dump-site-{a,b,c}.jpg`; never commit the live number as text.
   - The call reaches a live, in-character operator.
   - Players identify the fictional case and request incident access; the operator then gives Flag 1 plus contractor credentials using the rubric in `OPERATOR_RUNBOOK.md`.

2. `/contractor-login`
   - Credentials come from the phone call.
   - Successful login opens `/contractor` and reveals Flag 1.

3. `/contractor`
   - Players download `soil-core-survey.tiff`.
   - The generated artifact is a real 1200x800 color soil-core survey TIFF with a password-protected ZIP appended.
   - The ZIP password is assembled from the facility and field-packet clues.
   - ZIP contents include Flag 2 and `site-photo.png`, a real 1200x800 field image.
   - Camera XMP identifies calibration profile `B0`; the blue least-significant-bit plane contains a QR code with base64url-wrapped raw-deflate JSON carrying archive access and Flag 3.

4. `/archive-login`
   - Credentials come from the final stego payload.
   - Successful login opens `/archive` and reveals Flag 3.

5. `/archive`
   - Players assemble the hidden route from an HTTP response header, HTML source comment, and migration-audit download.
   - The JSONL audit interleaves four batches. Each discovery event exposes a root trace and span; child events omit the batch name.
   - Players follow the `JANUS-7C` trace through separate gateway, IAM, profile, and case-index spans, then combine those records with the earlier contractor roster.

6. `/ops/bracken-ridge/mercury-hollow/superadmin`
   - Successful login reveals Flag 4 and unlocks the final PDF download.

7. `/challenge-downloads/final-remediation-report.pdf`
   - The PDF password is assembled by resolving three VLT-3 company-record references from prior stages.
   - After unlocking it, base64 in the metadata `Subject` field points to the embedded `closure-manifest.json` attachment.
   - The attachment contains shuffled hex fragments. The second PDF page defines the document-control sequence used to reconstruct Flag 5.

## Canonical Answers

All credentials, flags, route values, and artifact passwords are defined once in
`src/challenge/challenge-manifest.json`. Do not duplicate or edit them in generated
artifacts. Keep that file and this repository unavailable to players.

## Artifact Generation

Run:

```bash
pnpm run challenge:artifacts
```

This creates:

- `public/downloads/soil-core-survey.tiff`
- `public/downloads/janus-migration-audit.jsonl`
- `public/downloads/final-remediation-report.pdf`

The generator requires the system `zip` command because the TIFF payload ZIP is password-protected.
Run `pnpm run challenge:validate` after generation. Validation checks TIFF rendering, appended ZIP extraction, blue-bit-plane QR recovery, compressed access JSON, JSONL trace linkage, PDF encryption, metadata, attachment extraction, fragment ordering, and final integrity.

## Live Event Replacement Points

- Staged photos are in place as `public/images/dump-site-a.jpg`, `dump-site-b.jpg`, and `dump-site-c.jpg`.
- Encode only the controlled event phone number in the real photos.
- Replace the generated site-photo artwork only if the blue-bit-plane embedding and `B0` XMP clue remain intact.
- Rebuild and validate the TIFF after replacing either generated image.
- Keep the generated PDF unless you replace it with a handmade artifact that passes the same password and metadata checks.
