param(
    [string]$Repo = "",
    [string]$EnvFile = ".env"
)

$ErrorActionPreference = "Stop"

function Get-GhPath {
    $command = Get-Command gh -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $defaultPath = "C:\Program Files\GitHub CLI\gh.exe"
    if (Test-Path $defaultPath) {
        return $defaultPath
    }

    throw "GitHub CLI was not found. Install GitHub CLI or add gh.exe to PATH."
}

function Invoke-Gh {
    param(
        [string[]]$Arguments
    )

    & $script:GhPath @Arguments
}

function Get-RepositorySlug {
    param(
        [string]$ExplicitRepo
    )

    if ($ExplicitRepo) {
        return $ExplicitRepo
    }

    $remote = git remote get-url origin 2>$null
    if (-not $remote) {
        throw "Could not determine origin remote. Pass -Repo owner/name explicitly."
    }

    if ($remote -match "github\.com[:/](.+?)(?:\.git)?$") {
        return $Matches[1]
    }

    throw "Could not parse GitHub repository slug from origin remote: $remote"
}

function Read-DotEnvFile {
    param(
        [string]$Path
    )

    $values = @{}
    if (-not (Test-Path $Path)) {
        return $values
    }

    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }
        $parts = $trimmed -split "=", 2
        if ($parts.Count -ne 2) {
            continue
        }
        $key = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        if ($key) {
            $values[$key] = $value
        }
    }

    return $values
}

function Set-GitHubSecretIfPresent {
    param(
        [string]$RepoSlug,
        [hashtable]$EnvValues,
        [string]$Name
    )

    $value = $EnvValues[$Name]
    if (-not $value) {
        Write-Host "Skipping secret $Name because it is not present in $EnvFile"
        return
    }

    Write-Host "Setting GitHub secret $Name"
    Invoke-Gh @("secret", "set", $Name, "--repo", $RepoSlug, "--body", $value) | Out-Null
}

function Set-GitHubVariable {
    param(
        [string]$RepoSlug,
        [string]$Name,
        [string]$Value
    )

    Write-Host "Setting GitHub variable $Name=$Value"
    Invoke-Gh @("variable", "set", $Name, "--repo", $RepoSlug, "--body", $Value) | Out-Null
}

$script:GhPath = Get-GhPath
$repoSlug = Get-RepositorySlug -ExplicitRepo $Repo

try {
    Invoke-Gh @("auth", "status") | Out-Null
}
catch {
    throw "GitHub CLI is installed but not logged in. Run: `"$script:GhPath`" auth login"
}

$envValues = Read-DotEnvFile -Path $EnvFile

$secretNames = @(
    "DATABASE_URL",
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "DB_SSLMODE",
    "SEC_CONTACT_NAME",
    "SEC_CONTACT_EMAIL"
)

foreach ($name in $secretNames) {
    Set-GitHubSecretIfPresent -RepoSlug $repoSlug -EnvValues $envValues -Name $name
}

$defaultVariables = @{
    "HISTORICAL_DATASET_LIMIT" = "25"
    "HISTORICAL_DATASET_OFFSET" = "0"
    "HISTORICAL_DATASET_BATCH_SIZE" = "10"
    "HISTORICAL_DATASET_MAX_BATCHES" = "3"
    "HISTORICAL_DATASET_APPROVAL_LIMIT" = "5"
    "HISTORICAL_DATASET_MARKET_PRE_DAYS" = "5"
    "HISTORICAL_DATASET_MARKET_POST_DAYS" = "5"
    "HISTORICAL_DATASET_STATUS" = "COMPLETED"
    "HISTORICAL_DATASET_SPONSOR" = ""
    "HISTORICAL_DATASET_PHASE" = ""
    "HISTORICAL_DATASET_STUDY_TYPE" = "INTERVENTIONAL"
    "HISTORICAL_DATASET_THERAPEUTIC_AREA" = ""
    "HISTORICAL_DATASET_HAS_RESULTS" = "true"
    "HISTORICAL_DATASET_WITHOUT_RESULTS" = "false"
    "HISTORICAL_DATASET_INCLUDE_EXISTING" = "false"
    "HISTORICAL_AUDIT_TOP_WARNING_LIMIT" = "10"
    "HISTORICAL_AUDIT_ISSUE_LIMIT" = "25"
    "HISTORICAL_AUDIT_THERAPEUTIC_AREA_LIMIT" = "10"
    "SPONSOR_MAPPING_REVIEW_EXPORT_LIMIT" = "100"
    "SPONSOR_MAPPING_REVIEW_EXPORT_OFFSET" = "0"
    "SPONSOR_MAPPING_REVIEW_EXPORT_STATUS" = ""
    "SPONSOR_MAPPING_REVIEW_EXPORT_TICKER" = ""
    "SPONSOR_MAPPING_REVIEW_EXPORT_REVIEWER_EMAIL" = ""
    "SPONSOR_MAPPING_REVIEW_EXPORT_FORMAT" = "json"
    "SPONSOR_MAPPING_REVIEW_EXPORT_INCLUDE_SUMMARY" = "true"
}

foreach ($entry in $defaultVariables.GetEnumerator()) {
    Set-GitHubVariable -RepoSlug $repoSlug -Name $entry.Key -Value $entry.Value
}

Write-Host ""
Write-Host "GitHub Actions configuration setup complete for repo $repoSlug"
