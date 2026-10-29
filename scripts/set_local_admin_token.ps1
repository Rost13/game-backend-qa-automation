$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$environmentPath = Join-Path $repositoryRoot '.env'
$examplePath = Join-Path $repositoryRoot '.env.example'

if (-not (Test-Path -LiteralPath $environmentPath)) {
    Copy-Item -LiteralPath $examplePath -Destination $environmentPath
}

$secureToken = Read-Host 'Paste PROMOCODES_ADMIN_BEARER_TOKEN (input is hidden)' -AsSecureString
$tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)

try {
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer).Trim()
    if ($token.StartsWith('Bearer ', [StringComparison]::OrdinalIgnoreCase)) {
        $token = $token.Substring(7).Trim()
    }
    if ([string]::IsNullOrWhiteSpace($token)) {
        throw 'Token cannot be empty.'
    }

    $lines = [Collections.Generic.List[string]]::new()
    $lines.AddRange([string[]](Get-Content -LiteralPath $environmentPath))
    $key = 'PROMOCODES_ADMIN_BEARER_TOKEN='
    $replaced = $false
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index].StartsWith($key, [StringComparison]::Ordinal)) {
            $lines[$index] = $key + $token
            $replaced = $true
            break
        }
    }
    if (-not $replaced) {
        $lines.Add($key + $token)
    }
    Set-Content -LiteralPath $environmentPath -Value $lines -Encoding utf8
    Write-Host 'Admin token saved to local ignored .env.' -ForegroundColor Green
    Write-Host 'You can close this window.' -ForegroundColor Green
}
finally {
    if ($tokenPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
    }
    $token = $null
}
