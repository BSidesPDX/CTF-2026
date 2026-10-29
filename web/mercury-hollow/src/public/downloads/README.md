# Protected Challenge Downloads

Files in this directory are served through session-gated controller routes, not as public static files.

Generate demo artifacts with:

```bash
pnpm run challenge:artifacts
```

Generated files:

- `soil-core-survey.tiff`: a 1200x800 color soil-core field survey with a password-protected ZIP appended to the end. The archive includes a second field image carrying compressed access JSON as a blue-bit-plane QR.
- `janus-migration-audit.jsonl`: interleaved migration events from several distributed traces. Players map the `JANUS-7C` root trace to gateway, IAM, profile, and case-index child spans.
- `final-remediation-report.pdf`: a two-page AES-256 PDF whose metadata points to an embedded closure manifest containing shuffled final-flag fragments.

Run `pnpm run challenge:validate` after replacing any file. Keep the filenames stable.
