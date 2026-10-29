# Social Engineering Site Challenge

## Challenge Flow

The BSides multi-stage challenge starts at `/incident` and follows this chain:

- staged incident photos -> phone call
- contractor login -> TIFF download
- TIFF with appended password-protected ZIP -> blue-bit-plane QR stego payload
- archive login -> route assembly from an HTTP header, HTML source, and audit log
- superadmin login -> encrypted PDF metadata, embedded manifest, and fragment reconstruction

Author notes and the full solve path are in `CHALLENGE_AUTHOR_NOTES.md`.

## To Run

- Copy env.example to .env
- update passwords, \*\_SECRET to be secret values
- generate artifacts with `pnpm run challenge:artifacts`
- validate the author solve with `pnpm run challenge:author-check`
- run the stack with `docker-compose up --build`

`src/challenge/challenge-manifest.json` is the canonical source for challenge
credentials, flags, route fragments, and artifact passwords. Keep the repository
private from players. Live-event procedures are in `OPERATOR_RUNBOOK.md`.
