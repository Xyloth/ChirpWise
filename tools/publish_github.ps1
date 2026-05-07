param(
    [string]$Owner = "Xyloth",
    [string]$RepoName = "ChirpWise",
    [switch]$Private
)

$ErrorActionPreference = "Stop"

$gh = "C:\Program Files\GitHub CLI\gh.exe"
if (!(Test-Path $gh)) {
    $gh = "gh"
}

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $gh auth status *> $null
$authExitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorActionPreference
if ($authExitCode -ne 0) {
    throw "GitHub CLI is not authenticated. Run 'gh auth login' or set GH_TOKEN, then rerun tools\publish_github.ps1."
}

$description = "Offline Android bird-sound trainer with real Xeno-canto recordings, regional quiz packs, and local progress tracking."
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
    $origin = git remote get-url origin 2>$null
    if ($LASTEXITCODE -eq 0 -and $origin) {
        git remote set-url origin "https://github.com/$repo.git"
    } else {
        git remote add origin "https://github.com/$repo.git"
    }
    git push -u origin $branch
} else {
    $visibility = if ($Private) { "--private" } else { "--public" }
    & $gh repo create $RepoName $visibility --source . --remote origin --push --description $description
}

try {
    & $gh repo edit $repo --description $description --add-topic android --add-topic birds --add-topic xeno-canto --add-topic sqlite --add-topic portfolio --add-topic audio
} catch {
    Write-Host "Repository was pushed. Topic update skipped because this gh version may not support --add-topic."
}

$visibilityLabel = if ($Private) { "private" } else { "public" }
Write-Host "Published $visibilityLabel repo: https://github.com/$repo"
