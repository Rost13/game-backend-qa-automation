$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$environmentPath = Join-Path $repositoryRoot '.env'
$examplePath = Join-Path $repositoryRoot '.env.example'

if (-not (Test-Path -LiteralPath $environmentPath)) {
    Copy-Item -LiteralPath $examplePath -Destination $environmentPath
}

$existingLines = [Collections.Generic.List[string]]::new()
$existingLines.AddRange([string[]](Get-Content -LiteralPath $environmentPath))
$userTokenKey = 'PROMOCODES_BEARER_TOKEN='
$adminTokenKey = 'PROMOCODES_ADMIN_BEARER_TOKEN='
$currentUserToken = $existingLines |
    Where-Object { $_.StartsWith($userTokenKey, [StringComparison]::Ordinal) } |
    Select-Object -First 1
$currentAdminToken = $existingLines |
    Where-Object { $_.StartsWith($adminTokenKey, [StringComparison]::Ordinal) } |
    Select-Object -First 1

if ($currentUserToken -and -not $currentAdminToken) {
    $existingLines.Add($adminTokenKey + $currentUserToken.Substring($userTokenKey.Length))
}

$secureToken = Read-Host 'Paste ordinary-user PROMOCODES_BEARER_TOKEN (input is hidden)' -AsSecureString
$tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)

try {
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer).Trim()
    if ($token.StartsWith('Bearer ', [StringComparison]::OrdinalIgnoreCase)) {
        $token = $token.Substring(7).Trim()
    }
    if ([string]::IsNullOrWhiteSpace($token)) {
        throw 'Token cannot be empty.'
    }

    $replaced = $false
    for ($index = 0; $index -lt $existingLines.Count; $index++) {
        if ($existingLines[$index].StartsWith($userTokenKey, [StringComparison]::Ordinal)) {
            $existingLines[$index] = $userTokenKey + $token
            $replaced = $true
            break
        }
    }
    if (-not $replaced) {
        $existingLines.Add($userTokenKey + $token)
    }
    Set-Content -LiteralPath $environmentPath -Value $existingLines -Encoding utf8
    Write-Host 'User token saved; existing token preserved as admin token.' -ForegroundColor Green
    Write-Host 'You can close this window.' -ForegroundColor Green
}
finally {
    if ($tokenPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
    }
    $token = $null
}
