# GitHub Repository Notes

This project is ready to initialize and publish as a GitHub repository.

Recommended repository description:

```text
Local-first bird sound trainer with Xeno-canto API v3 ingestion, license-aware SQLite storage, searchable library, and quiz mode.
```

Recommended topics:

```text
birds, birding, xeno-canto, audio, sqlite, python, quiz, desktop-app
```

Publish flow once GitHub CLI is installed and authenticated:

```powershell
git init
git add .
git commit -m "Initial bird sound trainer"
gh repo create bird-sound-trainer --public --source . --remote origin --push
```

Do not commit a real Xeno-canto key. Use `XENO_CANTO_API_KEY` locally.

