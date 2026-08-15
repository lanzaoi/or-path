# Tube B source-data audit — 2026-08-13

## Conclusion

The public repository does not contain the original Tube B CSV/XLSX attachments. This is not a local clone or PATH problem. Until an authorized teammate supplies the inputs, Tube solving must return `BLOCKED`; no fixture, archived output, or prose document may be presented as a fresh solve.

## Checks performed

- Inspected the current `fixtures/t3/tube_cut_b2026/` tree.
- Searched every Git object and the full path history for CSV/XLSX source files.
- Checked all public tags (`v0.2.0`, `v0.3.0`, `v0.3.1`).
- Checked the public GitHub fixture tree and release notes.

Expected filenames and placement are recorded in `fixtures/t3/tube_cut_b2026/DATA_REQUIRED.md`.

## Public evidence

- Fixture tree: https://github.com/lanzaoi/or-path/tree/main/fixtures/t3/tube_cut_b2026
- Releases: https://github.com/lanzaoi/or-path/releases
- v0.3.0 release: https://github.com/lanzaoi/or-path/releases/tag/v0.3.0

The v0.3.0 release notes explicitly describe the package as source/light metadata and exclude the contest PDF/full outputs. Historical statements that Tube LIVE passed on the author's machine are evidence of an unpublished local dataset, not evidence that the attachment exists in this repository.

## Recovery rule

Accept the data only from the responsible person or another authorized source, preserve the original filenames, place it under `fixtures/t3/tube_cut_b2026/raw/`, and run `orpath.bat tube-live-gate`. Do not infer or reconstruct confidential production quantities from archived outputs.
