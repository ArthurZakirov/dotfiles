<a id="managed-rules"></a>
# 🧰 Managed repositories, skills, and global rules

| When | Then |
| --- | --- |
| Using or refreshing a repository on another physical computer. | Treat that computer as an independent checkout state. Inspect local changes and divergence before receiving committed changes; use a safe fast-forward/update path that preserves local work. |
| Creating or modifying a managed skill. | Edit only the canonical repository `skills/` source, never a generated global installation or legacy alias. Review, validate, commit, and push the repository source before refreshing generated installations. |
| Updating generated skill installations on a machine. | Use SkillPort's documented maintenance flow and the canonical registry's selected skill subset. Treat generated installs as per-OS outputs, not independent editing sources. |
| Creating or changing global agent guidance. | Edit the canonical components declared by `agents-md-manifest.yaml`, not generated global `AGENTS.md` output. Preserve and reconcile existing non-generated guidance before a first replacement. |
| Adding support for another harness or agent product. | Keep canonical storage harness-neutral and avoid another editable skill copy. Verify that harness's actual skill-discovery and global-rule conventions instead of assuming universal paths/import syntax. |
| Deciding repository ownership, publication/privacy boundaries, or where reusable personal context belongs. | Read [agents-md-references/repository-routing-and-data-boundaries.md](agents-md-references/repository-routing-and-data-boundaries.md) before deciding. |
| Downloading, creating, editing, merging, converting, signing, scanning, exporting, or otherwise processing personal documents or personal data files, including PDFs, CSVs, spreadsheets, or bank exports. | Read [agents-md-references/personal-document-workflow.md](agents-md-references/personal-document-workflow.md) before acting. |
