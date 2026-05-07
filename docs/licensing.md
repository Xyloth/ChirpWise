# Licensing Notes

The app treats license metadata as product data, not comments.

Each recording row stores:

- source name
- source recording ID
- source URL
- recordist
- license name
- license URL
- generated attribution text

## Policy Checks

`ingest.birdtrainer.license_policy.evaluate_license` detects common Creative Commons constraints:

- `NC` / NonCommercial
- `ND` / NoDerivatives
- `CC0` / public domain

The pipeline can reject NC recordings for commercial builds and rejects ND recordings when normalization or clipping would create a derivative.

When `attach-original-clips` is used, the quiz plays the downloaded original recording directly. That path avoids creating a derivative copy, though redistribution still has to follow each recording's Creative Commons terms.

## Distribution Rule

Do not distribute a built dataset until `data/manifests/license_manifest.json` has been reviewed and the build policy matches the intended use.

For a commercial-safe dataset, run query/build stages with `--commercial-build --exclude-nc`, and keep derivative operations restricted to licenses that permit derivatives.

## Paid App Audit

Run the commercial audit whenever bundled audio changes:

```powershell
python tools/license_audit.py
```

The current full offline Android pack has 1,114 real Xeno-canto clips. Under the conservative paid-app rule, where every 20-second practice clip is treated as modified/adapted:

- 20 clips are safe for a paid trimmed build.
- 1,094 clips need replacement audio or explicit recordist permission.
- The safe set is CC0, CC BY, and CC BY-SA.
- CC BY-SA is usable only if the adapted clip remains under the same ShareAlike terms.
- NC licenses are excluded for paid distribution.
- ND licenses are excluded because the app distributes trimmed clips.

Audit outputs:

- `docs/audits/commercial-license-audit.md`
- `docs/audits/commercial-license-audit.csv`
- `docs/audits/commercial-license-audit.json`

## Replacement Source Coverage

Run the no-email source mapper when evaluating a paid build:

```powershell
python tools/commercial_source_coverage.py
```

Current result for the 1,161-species North America taxonomy:

- 626 species have strict no-email commercial-safe coverage from Xeno-canto, NPS, or Wikimedia Commons.
- 804 species have coverage if iNaturalist research-grade CC0/BY/BY-SA sound candidates are accepted after manual listening QC.
- 357 species are still missing after these no-email sources.

Coverage outputs:

- `docs/audits/commercial-source-coverage.md`
- `docs/audits/commercial-source-coverage.csv`
- `docs/audits/commercial-source-coverage.json`
