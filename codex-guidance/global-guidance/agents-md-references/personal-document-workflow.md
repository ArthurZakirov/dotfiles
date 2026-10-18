# Personal document and data-file workflow

Use these rules after the parent `AGENTS.md` has selected this reference for work on Arthur's personal documents or personal data files.

## Canonical storage

- Google Drive is the durable source of truth for personal document binaries and exported personal data files. Do not leave durable copies scattered across the local filesystem or Git repositories.
- `PDF Documents` is for administrative or official PDFs: forms, contracts, scanned letters, correspondence, submissions, and documents exchanged with authorities, companies, landlords, or other institutions.
- `PDF Personal` is for personal PDFs such as handwritten notes, book notes, and private scans outside administrative or institutional workflows. Keep these categories separate.
- For non-PDF personal data files, such as bank CSV/XLSX exports, use the appropriate canonical Google Drive location for that domain rather than a source-code repository. Do not invent a durable local folder merely because no Drive location is immediately visible.

## Medallion-style stages

When a workflow creates derivatives, preserve stage semantics instead of overwriting the source:

1. **Raw** — the original downloaded, scanned, exported, or user-provided file. Keep it unchanged.
2. **Processed** — merged, filled, converted, normalized, redacted, signed, concatenated, or otherwise transformed derivatives.
3. **Final** — the exact artifact intended for submission, sharing, printing, or durable reference, when that is meaningfully distinct from Processed.

Within the relevant Google Drive domain, keep Raw and Processed/Final material distinguishable. Reuse an existing stage structure when one already exists; do not create parallel competing folder conventions.

## Local staging

- Local copies are allowed only when required for processing, previewing, rendering, signing, upload handoff, or a tool that cannot operate directly on Drive.
- Use only the gitignored local workspace inside `self-source`: `.local-workspace/documents/`. Never put personal working files in another repository, including `ArthurZakirov`, `arthur-zakirov`, or whichever repository happens to be the current working directory.
- Mirror stage semantics locally with `.local-workspace/documents/raw/`, `.local-workspace/documents/processed/`, and `.local-workspace/documents/final/` when useful. These directories are transient staging, not canonical storage.
- Never commit or force-add anything under `.local-workspace/`.
- As soon as the intended durable artifact is safely stored in the correct Google Drive location, delete the corresponding local source copies, renders, intermediate files, drafts, signatures, and outputs that are no longer needed. The normal end state is an empty local staging workspace.

## Handling and cleanup

- Do not infer storage ownership from a folder or repository name. Decide from the documented storage policy and the file's purpose.
- Do not silently discard the only copy of an original. Confirm the durable Drive copy exists before cleanup when deletion would otherwise remove the sole copy.
- Avoid unnecessary duplication: download only the files needed for the current operation and clean up task-specific staging promptly.
- Keep secrets and ultra-sensitive credentials out of Git and ordinary document staging; follow the dedicated secrets/password-manager workflow for those values.
