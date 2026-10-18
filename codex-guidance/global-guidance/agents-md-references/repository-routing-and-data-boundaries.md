# Repository routing and data boundaries

Use these rules after the parent `AGENTS.md` has selected this reference for a task involving repository ownership, publication/privacy boundaries, or locating Arthur's reusable personal context.

## self-source

`self-source` is Arthur's private personal source of truth for reusable facts and context that agents need to act on his behalf without repeatedly asking for the same information.

Use it for information such as:

- identity, contact, address, residence-history, landlord, apartment, contract, and recurring administrative facts;
- reusable values and policies needed for online forms, PDF forms, registrations, government/admin workflows, and applications;
- context needed to draft personal emails or messages, such as the correct landlord, contact person, contract reference, apartment number, or address;
- personal context that materially improves local research or recommendations, such as the correct home location for nearby services;
- document manifests or references that tell an agent where externally stored documents can be found.

Do not use `self-source` for agent setup, repository inventories, cross-device synchronization, skill distribution, generic workflow instructions, or reusable public methods. Those belong in the relevant public technical repository.

Load only the smallest relevant part of `self-source` for the current task. Do not treat the repository as context that should be loaded wholesale.

## Data boundaries

Personal does not automatically mean private. Publication depends on concrete privacy, security, confidentiality, and harm risk plus the intended repository's purpose.

- Ordinary private facts needed for forms and personal workflows may be versioned in `self-source` when a private Git repository is an acceptable protection boundary.
- Large or sensitive documents such as certificates, identity scans, income proofs, contracts, and similar PDFs should normally live in the appropriate external document store; `self-source` should keep only the metadata or references needed to locate and use them.
- Secrets and ultra-sensitive credentials must not be committed to `self-source` or another Git repository. This includes passwords, one-time codes, API/private keys, payment-card data, bank credentials, tax or national-ID secrets, passport secrets, and account-recovery material. Use the approved secrets/password-manager workflow instead.
- Do not invent missing personal facts. Retrieve them from the relevant canonical source or ask Arthur when necessary.
- Do not copy private facts into public repositories merely to make a workflow convenient.
- After moving information to a new canonical source, remove stale parallel copies and update loaders/references.

### PDF storage and temporary processing

- Google Drive is Arthur's canonical store for PDF documents. Use `PDF Documents` for administrative or official material such as forms, contracts, scanned letters, correspondence, and documents for authorities, companies, landlords, or other institutions. Use `PDF Personal` for personal material such as handwritten notes, book notes, and other private scans. Do not mix the two categories.
- A Git repository or the current working directory is not a document store. Never infer that a repository or folder is suitable for personal documents from its name, including names such as `ArthurZakirov` or `arthur-zakirov`.
- If PDF manipulation requires local files, including merging, rendering, conversion, or form processing, use the gitignored `self-source/.local-workspace/documents/` staging area defined in the [personal document workflow](personal-document-workflow.md). Treat downloaded inputs, page renders, intermediate PDFs, and drafts as temporary artifacts; never commit them.
- Save the intended final PDF to the correct Google Drive folder and remove the temporary local artifacts after the final document is safely stored. Do not leave durable duplicate PDFs scattered across local project folders.

## Repository routing

The canonical machine-readable inventory of managed repositories, their exact GitHub sources, checkout roles, refresh participation, and skill-distribution status is [repositories.json](repositories.json). Read it when exact repository routing matters.

Use repository purpose, not convenience, to decide ownership. A file belongs where its durable responsibility lives, not merely in the repository that happens to be open when the information is discovered.
