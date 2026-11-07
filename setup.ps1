# -*- coding: utf-8 -*-
param(
    [string]$TokenFile,
    [switch]$SkipGitHub
)
# Скрипт начальной настройки: BOT_TOKEN / BOT_TOKEN_OWNERS.
# Источники по порядку: 1) окружение 2) токены.txt 3) секреты проекта
# (GitHub Secrets через gh: наличие через gh secret list; update через
# gh secret set) 4) ручной ввод (скрытый, без эха).
# Значения НИКОГДА не печатаются ни в окно, ни в лог, ни в чат.
$ErrorActionPreference = 'Stop'
if (-not $TokenFile) { $TokenFile = Join-Path $PSScriptRoot 'токены.txt' }
$names = @('BOT_TOKEN', 'BOT_TOKEN_OWNERS')

function Read-TokenFile($path) {
    if (-not (Test-Path $path)) { return @{} }
    $map = @{}
    foreach ($line in (Get-Content -LiteralPath $path -Encoding UTF8)) {
        if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
        $eq = $line.IndexOf('=')
        $key = $line.Substring(0, $eq).Trim()
        $val = $line.Substring($eq + 1).Trim()
        if ($key) { $map[$key] = $val }
    }
    return $map
}

function Read-Secret($name) {
    Write-Host "Введите $name (ввод скрыт, пустая строка — пропустить): " -NoNewline
    if ([Console]::IsInputRedirected) {
        $raw = [Console]::In.ReadLine()
    } else {
        $sec = Read-Host '' -AsSecureString
        $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
        try {
            $raw = [System.Runtime.InteropServices.Marshal]::PtrToStringUni($bstr)
        } finally {
            [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
    }
    if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
    return $raw.Trim()
}

function Merge-TokenFile($path, $name, $value) {
    $lines = @()
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    if (Test-Path $path) {
        $lines = [System.IO.File]::ReadAllLines($path, $utf8)
    }
    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        $eq = $lines[$i].IndexOf('=')
        if ($eq -gt 0 -and $lines[$i].Substring(0, $eq).Trim() -eq $name) {
            $lines[$i] = "$name=$value"
            $found = $true
        }
    }
    if (-not $found) { $lines += "$name=$value" }
    [System.IO.File]::WriteAllLines($path, $lines, $utf8)
}

# Синхронизация секретов в GitHub (значения не выводятся, только имена).
function Sync-GitHubSecret($name, $value) {
    if ($SkipGitHub) { return $false }
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { return $false }
    $null = & gh secret set $name --body $value 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "${name}: секрет GitHub обновлён (значение не напечатано)"
        return $true
    }
    Write-Host "${name}: не удалось обновить GitHub Secrets (gh auth проверьте)"
    return $false
}

$fromGitHub = @{}
if (-not $SkipGitHub -and (Get-Command gh -ErrorAction SilentlyContinue)) {
    $list = (& gh secret list --json name 2>$null | ConvertFrom-Json) -as [array]
    if ($LASTEXITCODE -eq 0 -and $list) {
        $ghNames = @($list | ForEach-Object { $_.name })
        foreach ($n in $names) {
            if ($ghNames -contains $n) { $fromGitHub[$n] = $true }
        }
    }
}

$values = @{}
$sources = @{}
foreach ($name in $names) {
    $value = [Environment]::GetEnvironmentVariable($name)
    $source = 'окружение'
    if ($value) {
        $values[$name] = $value
    } else {
        $tokenMap = Read-TokenFile $TokenFile
        if ($tokenMap.ContainsKey($name) -and $tokenMap[$name]) {
            $value = $tokenMap[$name]
            $source = 'токены.txt'
            $values[$name] = $value
        } else {
            $value = Read-Secret $name
            if ($value) {
                $source = 'ручной ввод'
                $values[$name] = $value
                if (-not ($tokenMap.ContainsKey($name) -and $tokenMap[$name])) {
                    Merge-TokenFile $TokenFile $name $value
                }
            }
        }
    }
    if ($value) { $sources[$name] = $source }
    if ($value) {
        $null = Sync-GitHubSecret $name $value
    }
}

Write-Host ''
Write-Host '=== Сводка ==='
foreach ($name in $names) {
    $local = if ($sources.ContainsKey($name)) { $true } else { $false }
    if ($local) {
        Write-Host "${name}: заполнен (источник: $($sources[$name]))" -ForegroundColor Green
    } else {
        Write-Host "${name}: не задан"
        if ($fromGitHub.ContainsKey($name)) {
            Write-Host "${name}: есть в GitHub Secrets (значение недоступно для чтения)," -ForegroundColor Yellow
            Write-Host '  workflow на GitHub получит его автоматически в Actions.'
        } else {
            Write-Host "${name}: нет ни локально, ни в GitHub Secrets" -ForegroundColor Red
        }
    }
}
Write-Host ''
Write-Host 'Значения не выводились (ни в окно, ни в лог).'
Write-Host "Локальный файл токенов: $TokenFile"
