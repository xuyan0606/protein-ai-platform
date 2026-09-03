# Enzyme DB Patent And Preprint Metadata Policy

Date: 2026-08-05

Scope: simplified three-table enzyme evidence SQLite databases under
`/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库`, with immediate focus on
`acid_protease` and `xylanase`.

## Problem

The compact enzyme databases use `papers.doi` and `papers.pmid` as journal
article identifiers. Patent rows and preprint rows do not always have DOI/PMID
identity that maps cleanly to the current local paper row:

- Patent rows such as `XYN67` and `XYN68` carry patent identifiers
  (`EP2305820`, `US20160168555`) in article-like fields.
- Preprint rows such as `AP605` may have both a preprint DOI and a later
  version-of-record DOI/PMID, but upgrading the row changes source type,
  journal, and citation identity.
- Boundary rows may have DOI values that point to unrelated papers or unresolved
  source-table payloads.

Therefore DOI/PMID backfill must stay separate from patent metadata capture,
preprint upgrade, and export-safe release.

## Non-Negotiable Rules

1. DOI/PMID writes require strong agreement across local title, DOI or PMID,
   author, journal, and year.
2. Patent identifiers are not DOI/PMID substitutes.
3. A preprint row must not be rewritten to a journal version-of-record unless
   the whole citation identity is upgraded under an explicit review decision.
4. `hold`, `boundary`, `non_exportable`, `patent`, and `preprint` markers block
   export-safe output even when `paper.quality='A'` and `measurement.conf='A'`.
5. A boundary repair may make a row safer for browsing, but it does not make the
   row export-safe. Export release needs a separate positive decision.

## Proposed Sidecar Object

Do not add fields to the compact SQLite schema until migration ownership is
clear. Store policy decisions in sidecar manifests first, then later migrate to
a normalized curation table if needed.

```json
{
  "family": "xylanase",
  "paper_id": "XYN67",
  "record_type": "patent",
  "source_identifier": "EP2305820",
  "source_identifier_type": "patent_publication",
  "doi": null,
  "pmid": null,
  "decision": "keep_doi_pmid_blank",
  "export_safe": false,
  "training_safe": false,
  "review_status": "manual_required",
  "evidence": {
    "local_title": "...",
    "local_author": "...",
    "local_year": 2011,
    "live_sources": []
  },
  "notes": "Patent identity is tracked separately from DOI/PMID."
}
```

For preprints:

```json
{
  "family": "acid_protease",
  "paper_id": "AP605",
  "record_type": "preprint_to_version_of_record",
  "preprint_doi": "10.64898/2026.01.31.703050",
  "version_of_record_doi": "10.34133/csbj.0159",
  "version_of_record_pmid": "42454103",
  "decision": "manual_identity_upgrade_required",
  "required_checks": [
    "title_match",
    "first_or_corresponding_author_match",
    "journal_year_update_approved",
    "variant_payload_still_maps_to_article",
    "boundary_and_export_release_reviewed"
  ],
  "export_safe": false,
  "training_safe": false
}
```

## Upgrade Workflow

1. Read local row and all linked variants/measurements.
2. Query DOI/PubMed/Europe PMC/Crossref live sources.
3. Compare title, author set, journal, year, DOI, PMID, and variant payload.
4. If only DOI/PMID is missing and all identity fields match, use the normal
   guarded metadata script.
5. If source type changes, create a sidecar policy decision first:
   `manual_identity_upgrade_required`.
6. Only after human review, run a guarded row-upgrade script that updates the
   full citation fields together.
7. Keep export-safe blocked until measurement-level evidence is also reviewed.

## Current Rows Covered

| Family | Row | Policy |
|---|---|---|
| xylanase | `XYN67` | patent sidecar candidate; keep DOI/PMID blank |
| xylanase | `XYN68` | patent sidecar candidate; keep DOI/PMID blank |
| acid_protease | `AP605` | preprint-to-version-of-record candidate; manual identity upgrade required |

## Implementation Status

- Current platform code blocks export-safe for `hold/boundary/non_exportable/patent/preprint` markers.
- `/data` metadata quality exposes patent/preprint/boundary/policy-excluded counts.
- This document defines the sidecar object and upgrade workflow.
- Persistent sidecar manifests are implemented beside each SQLite DB:
  - `acid-protease-db/enzyme_metadata_policy_decisions_20260805.json`
  - `xylanase-db/enzyme_metadata_policy_decisions_20260805.json`
- The platform status API reads these sidecars into
  `metadata_policy_decisions`, including manifest count, decision count,
  record types, and review statuses.
- Future work: if these decisions become editable in the UI, migrate them to a
  normalized curation table or bind them to the existing curation queue.
