# push-most.ps1 — публикация файлов моста в публичный репо-почту (realtor-most)
# Файлы моста лежат в корне репо-почты: status.md, ochered-komand.txt, serdce.txt (+ README.md)
$repo = "isaafoks-collab/realtor-most"
$most = Join-Path $PSScriptRoot ""   # папка most
$files = @("status.md", "ochered-komand.txt", "serdce.txt", "README.md")

foreach ($name in $files) {
    $local = Join-Path $most $name
    if (-not (Test-Path $local)) { Write-Host "нет файла: $name"; continue }
    $bytes = [System.IO.File]::ReadAllBytes($local)
    $b64 = [Convert]::ToBase64String($bytes)
    # sha текущей версии на удалённой стороне (для update); если файла нет — create
    $sha = $null
    $cur = gh api "repos/$repo/contents/$name" 2>$null | ConvertFrom-Json
    if ($cur -and $cur.sha) { $sha = $cur.sha }
    $payload = @{ message = "most: update $name"; content = $b64 }
    if ($sha) { $payload["sha"] = $sha }
    $json = $payload | ConvertTo-Json -Compress
    $tmp = Join-Path $env:TEMP "put-$name.json"
    # tmp-файл перезаписываем байтами, чтобы не затереть кириллицу cp1251
    [System.IO.File]::WriteAllBytes($tmp, [Text.Encoding]::UTF8.GetBytes($json))
    $resp = gh api "repos/$repo/contents/$name" -X PUT --input $tmp -H "Content-Type: application/json" 2>&1
    if ($LASTEXITCODE -eq 0) { Write-Host "pushed: $name" } else { Write-Host "FAIL: $name -> $resp" }
    Remove-Item $tmp -ErrorAction SilentlyContinue
}
