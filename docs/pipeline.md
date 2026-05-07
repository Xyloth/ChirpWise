# Data Pipeline

The builder is intentionally staged so each step can be audited, retried, or replaced.

## 1. Import Taxonomy

Input: CSV with at least common name and scientific name columns.

Accepted header variants include:

- `common_name`, `Common Name`, `English Name`
- `scientific_name`, `Scientific Name`, `Latin Name`
- `ebird_code`, `Species Code`, `Taxon Code`
- `family`, `order`, `range_notes`

Command:

```powershell
python -m ingest.birdtrainer.cli import-taxonomy data/raw/taxonomy/taxonomy.csv --source "eBird/Clements" --version "2025" --scope "US+Canada"
```

## 2. Query Xeno-canto API v3

The query stage writes metadata JSON per species under `data/raw/xeno_metadata/`. It does not download audio.

Command:

```powershell
$env:XENO_CANTO_API_KEY = "your-key"
python -m ingest.birdtrainer.cli query-xeno --country "United States" --country "Canada" --quality A --quality B --sound-type song --sound-type call
```

API v3 requires the key as a `key` query parameter on every request. Queries must use search tags such as `sp:"Cardinalis cardinalis"`, `grp:birds`, `cnt:"United States"`, `q:A`, and `type:song`.

To get a key:

1. Register or sign in at `https://xeno-canto.org/`.
2. Verify your email address.
3. Open `https://xeno-canto.org/account`.
4. Copy the API key from your account page.
5. Keep it out of GitHub and use `XENO_CANTO_API_KEY` or `.env`-style local storage.

## 3. Ingest Metadata

Command:

```powershell
python -m ingest.birdtrainer.cli ingest-xeno-metadata
```

This creates `recordings` rows with source IDs, source URLs, location, quality, sound type, license fields, and generated attribution text.

## 4. Download Originals

Command:

```powershell
python -m ingest.birdtrainer.cli download-audio
```

Original files are stored under `data/raw/xeno_audio_original/` and are never modified in place.

## 5. Normalize App Audio

Command:

```powershell
python -m ingest.birdtrainer.cli normalize-audio --codec opus
```

This requires `ffmpeg`. The code checks each recording license before creating derivative audio and skips NoDerivatives recordings when derivative output is required.

## 6. Segment Quiz Clips

Command:

```powershell
python tools/create_training_clips.py --seconds 20 --bitrate 96k
```

Generated clips are stored under `data/processed/training_clips_20s/`. Clip rows retain recording IDs, species IDs, clip type, difficulty, and derivative status.

If `ffmpeg` is not available, use original downloaded files directly:

```powershell
python -m ingest.birdtrainer.cli attach-original-clips
```

That keeps audio unmodified, which is also the right fallback for recordings whose license does not permit derivatives.

## 6.5 Android Regional Pack

The Android V1 pack is built from the Northeast / Ohio Valley Xeno-canto region list, then backfilled for local species that have regional recordings but no local clip yet:

```powershell
python tools/update_region_membership_from_xeno.py --region northeast
python tools/backfill_region_audio.py --region northeast
python tools/create_training_clips.py --seconds 20 --bitrate 96k
python tools/build_android_assets.py --region northeast --pack-name "Northeast / Ohio Valley" --clean
```

## 7. Reports

Commands:

```powershell
python -m ingest.birdtrainer.cli build-database --taxonomy-source "eBird/Clements" --taxonomy-version "2025" --scope "US+Canada"
python -m ingest.birdtrainer.cli coverage-report
python -m ingest.birdtrainer.cli license-manifest
```

Outputs:

- `data/manifests/coverage_report.csv`
- `data/manifests/license_manifest.json`
- `dataset_builds` rows inside SQLite
