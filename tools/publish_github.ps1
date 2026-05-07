param(
    [string]$Owner = "Xyloth",
    [string]$RepoName = "ChirpWise"
)

$ErrorActionPreference = "Stop"

$gh = "C:\Program Files\GitHub CLI\gh.exe"
if (!(Test-Path $gh)) {
    $gh = "gh"
}

& $gh auth status | Out-Null

$description = "Offline bird-sound trainer with Xeno-canto ingestion, regional Android packs, and local progress tracking."
$repo = "$Owner/$RepoName"
$branch = (git branch --show-current).Trim()
$exists = $false

try {
    & $gh repo view $repo | Out-Null
    $exists = $true
} catch {
    $exists = $false
}

if ($exists) {
    git remote remove origin 2>$null
    git remote add origin "https://github.com/$repo.git"
    git push -u origin $branch
} else {
    & $gh repo create $RepoName --private --source . --remote origin --push --description $description
}

try {
    & $gh repo edit $repo --description $description --add-topic android --add-topic birds --add-topic xeno-canto --add-topic sqlite --add-topic portfolio --add-topic audio
} catch {
    Write-Host "Repository was pushed. Topic update skipped because this gh version may not support --add-topic."
}

Write-Host "Published private repo: https://github.com/$repo"
