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
