# Bird Sound Trainer

Local-first bird-sound trainer for building, browsing, and quizzing against a license-aware bird audio library.

This repository is organized around the product spine:

```text
taxonomy -> audio acquisition -> license tracking -> normalized library -> searchable UI -> quiz engine
```

The app runs locally with Python and SQLite. It ships with a small generated fixture dataset so the UI and quiz engine work immediately. Real bird recordings are acquired through the Xeno-canto API v3 ingestion pipeline after you provide an API key.

## Quick Start

```powershell
python tools/run_app.py
```

Open:

```text
http://127.0.0.1:8765
```

If `python` points to an older interpreter, use Python 3.12+.

## Desktop Launcher

After packaging, use:

```text
dist/BirdSoundTrainer/BirdSoundTrainer.exe
```

The desktop shortcut created by `tools/create_desktop_shortcut.ps1` points to that executable when it exists, otherwise it points to the local Python launcher.

## What Is Included

- Local SQLite database with normalized species, recordings, clips, progress, attribution, and similarity tables.
- Static desktop-style app UI: dashboard, browse/search, species detail, quiz, progress, coverage, attributions, and settings.
- Local HTTP API with no external runtime dependencies.
- Data builder modules for taxonomy import, Xeno-canto querying, metadata persistence, audio conversion, clip generation, database build, and coverage reporting.
- License policy checks that treat attribution, NC, ND, and derivative rules as first-class data.
- Real Xeno-canto audio clips when the local dataset has been built with an API key.
- Four broad training regions, documented in `docs/regions.md`.

## Real Dataset Flow

1. Download an eBird/Clements or compatible taxonomy CSV.
2. Put it under `data/raw/taxonomy/`.
3. Get and set your Xeno-canto API v3 key:

   - Register at `https://xeno-canto.org/` if you do not already have an account.
   - Verify your email address.
   - Go to `https://xeno-canto.org/account`.
   - Copy the API key shown on the account page.
   - Do not commit it to GitHub.

```powershell
$env:XENO_CANTO_API_KEY = "your-key"
```

4. Import taxonomy:

```powershell
python -m ingest.birdtrainer.cli import-taxonomy data/raw/taxonomy/your_taxonomy.csv --scope "US+Canada"
```

5. Query Xeno-canto API v3:

```powershell
python -m ingest.birdtrainer.cli query-xeno --limit-species 25 --country "United States" --country "Canada"
```

6. Download originals:

```powershell
python -m ingest.birdtrainer.cli download-audio
```

7. Build app-ready audio and clips. If `ffmpeg` is unavailable, attach original downloaded recordings directly as playable quiz audio:

```powershell
python -m ingest.birdtrainer.cli attach-original-clips
```

With `ffmpeg` installed, you can instead normalize and segment:

```powershell
python -m ingest.birdtrainer.cli normalize-audio
python -m ingest.birdtrainer.cli segment-clips
```

8. Build the SQLite database and reports:

```powershell
python -m ingest.birdtrainer.cli build-database
python -m ingest.birdtrainer.cli coverage-report
```

## Optional Tools

`ffmpeg` is recommended for real audio normalization, opus/m4a export, and clip segmentation. The pipeline detects it at runtime and explains what could not be completed if it is absent. Fixture clips are generated as browser-playable WAV files and do not require ffmpeg.

## One-Command Real Audio Build

For the current starter species list:

```powershell
$env:XENO_CANTO_API_KEY = "your-key"
python tools/build_real_dataset.py --limit-species 12
```

This queries API v3, imports metadata, downloads real recordings, attaches originals as quiz audio, removes generated fixture clips after real clips exist, and rebuilds coverage/license reports.

## Portable Windows Build

```powershell
python -m pip install pyinstaller
python -m PyInstaller BirdSoundTrainer.spec
```

Copy the entire `dist/BirdSoundTrainer/` folder to a flash drive. The executable depends on the adjacent `_internal` folder that contains the local app, database, audio, and manifests.

## Android Direction

The right Android product shape is a region-pack app, not one giant bundled audio archive. The default pack should be `Northeast / Ohio Valley`, with optional downloads for the other three regions. Current desktop data already uses 20-second MP3 practice clips so it can feed that Android app without shipping multi-GB original recordings.

## License Hygiene

Every recording carries:

- `license_name`
- `license_url`
- `recordist`
- `source_url`
- `source_recording_id`
- generated `attribution_text`

The pipeline skips derivative operations for NoDerivatives licenses and can filter out NonCommercial licenses for commercial-safe builds.

## Project Layout

```text
ingest/
  birdtrainer/        Python ingestion and database package
  *.py                Thin command wrappers matching the data pipeline stages
data/
  raw/                Taxonomy, Xeno-canto metadata, original audio
  processed/          App audio, clips, spectrogram/waveform artifacts
  manifests/          Coverage and license reports
  app/                SQLite database
app/                  Static local UI
server/               Local HTTP API/server
tools/                Launch and utility scripts
tests/                Stdlib test suite
docs/                 Pipeline and licensing notes
```
