# strazh.ps1 — страж моста «слон и рыбки» (realtor-service)
# Живёт в фоне, раз в минуту: собирает команды из GitHub, ловит лимит, перезапускает агента,
# следит за эшелонами каскада (freellmapi/OmniRoute/Ollama) и поднимает умершие
$ErrorActionPreference = "Continue"

$proj    = "C:\Users\Андрей\Documents\realtor-service"
$most    = Join-Path $proj "most"
$status  = Join-Path $most "status.md"
$serdce  = Join-Path $most "serdce.txt"
$ochered = Join-Path $most "ochered-komand.txt"
$log     = Join-Path $most "strazh-log.txt"
$repo    = "isaafoks-collab/realtor-most"      # публичный репо-почта (https://github.com/isaafoks-collab/realtor-most)
$fllDir  = "C:\Users\Андрей\Documents\agent-tools\freellmapi"
$fllLog  = "$env:USERPROFILE\.freellmapi"
$omniLog = "$env:USERPROFILE\.omniroute\logs"
$fllKey  = ""                                # заполняется из БД freellmapi при проверке живости

function Log($m) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $m" | Add-Content $log }

# один экземпляр стража
$mutex = New-Object System.Threading.Mutex($false, "Global\strazh-realtor")
if (-not $mutex.WaitOne(0)) { exit }

function PortOtkryt([int]$p) {
    $c = New-Object Net.Sockets.TcpClient
    try { $c.Connect("127.0.0.1", $p); return $true } catch { return $false } finally { $c.Close() }
}

function SerdceStale([int]$min) {
    if (-not (Test-Path $serdce)) { return $true }
    return ((Get-Date) - (Get-Item $serdce).LastWriteTime).TotalMinutes -gt $min
}
function OpenCodeZhiv {
    return ($null -ne (Get-Process opencode* -ErrorAction SilentlyContinue))
}
function Zapustit($prompt) {
    Log "запуск OpenCode: $prompt"
    $cmd = "cd /d '$proj' && opencode run -c --auto `"$prompt`""
    Start-Process cmd.exe -ArgumentList "/c", $cmd -WindowStyle Hidden
}

# --- эшелоны каскада ---

function FreellmZhiv {
    if (-not (PortOtkryt 3001)) { return $false }
    try {
        $k = (python -c "import sqlite3;print(sqlite3.connect(r'$fllDir/server/data/freeapi.db').execute('SELECT value FROM settings WHERE key=''unified_api_key''').fetchone()[0])" 2>$null)
        if (-not $k) { return $true }  # порт открыт, ключ не прочитать — считаем живым
        $h = Invoke-WebRequest -Uri "http://127.0.0.1:3001/healthz" -Headers @{Authorization="Bearer $k"} -UseBasicParsing -TimeoutSec 10
        return ($h.StatusCode -lt 500)
    } catch { return $true }  # порт открыт, но эндпоинта нет — живой
}
function PodnyatFreellm {
    Log "поднимаю freellmapi (3001)"
    New-Item -ItemType Directory -Force $fllLog | Out-Null
    Start-Process cmd.exe -ArgumentList "/c", "cd /d '$fllDir' && node server\dist\index.js > $fllLog\stdout.log 2> $fllLog\stderr.log" -WindowStyle Hidden
}
function OmniZhiv { return (PortOtkryt 20128) }
function PodnyatOmni {
    Log "поднимаю OmniRoute (20128)"
    Start-Process cmd.exe -ArgumentList "/c", "omniroute serve --headless > $omniLog\stdout.log 2> $omniLog\stderr.log" -WindowStyle Hidden
}
function OllamaZhiv { return (PortOtkryt 11434) }
function PodnyatOllama {
    Log "поднимаю Ollama (11434)"
    Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama app.exe" -WindowStyle Hidden
}
function ClaudeMemZhiv { return (PortOtkryt 37792) }
function PodnyatClaudeMem {
    Log "поднимаю claude-mem (37792)"
    Start-Process cmd.exe -ArgumentList "/c", "npx -y claude-mem@latest start > $env:USERPROFILE\.claude-mem-strazh.log 2>&1" -WindowStyle Hidden
}

# Strix в Docker и полигоны НЕ считаются молчанием сердца
function RobotyBezAgenta {
    if (Get-Process strix*, docker* -ErrorAction SilentlyContinue) { return $true }
    $d = Get-Command docker -ErrorAction SilentlyContinue
    if ($d) {
        $names = docker ps --format "{{.Names}}" 2>$null
        if ($names -and ($names -match "strix|poligon")) { return $true }
    }
    if (Test-Path (Join-Path $most "poligon-aktiv.flag")) { return $true }
    return $false
}

while ($true) {
    try {
        # 1. Команды из GitHub Issues
        $raw = gh issue list -R $repo --label komanda --state open --json number,title 2>$null
        if ($raw) {
            foreach ($i in ($raw | ConvertFrom-Json)) {
                gh issue close $i.number -R $repo | Out-Null
                Add-Content $ochered ("[" + (Get-Date -Format 'MM-dd HH:mm') + " issue" + $i.number + "] " + $i.title)
                Log "команда из issue $($i.number) в очереди"
            }
        }

        # 2. Эшелоны: умерший — поднять
        if (-not (FreellmZhiv)) { PodnyatFreellm; Start-Sleep 20 }
        if (-not (OmniZhiv))    { PodnyatOmni; Start-Sleep 20 }
        if (-not (OllamaZhiv))  { PodnyatOllama; Start-Sleep 20 }
        if (-not (ClaudeMemZhiv)) { PodnyatClaudeMem; Start-Sleep 20 }

        # 3. Лимит: если внизу есть топливо (эшелон 2/3 жив) — перезапускаем сразу
        #    с командой переключиться вниз; ждать сброса только если дно тоже пусто
        if (Test-Path $status) {
            $st = Get-Content $status -Raw
            if ($st -match "СОСТОЯНИЕ:\s*ЖДУ ЛИМИТ" -and $st -match "СБРОС:\s*(\d{1,2}):(\d{2})") {
                $niz = (OmniZhiv -or FreellmZhiv -or OllamaZhiv)
                if ($niz) {
                    Log "лимит на эшелоне 1, внизу есть топливо — переключение эшелона"
                    Zapustit "Ты слон. Лимит эшелона 1 сбрасывается позже. Внизу есть топливо: freellmapi (127.0.0.1:3001) и OmniRoute (127.0.0.1:20128) живы, Ollama (127.0.0.1:11434, qwen2.5-coder:3b) — дно. Продолжай работу на эшелоне 2 или 3, записав в most/status.md строку ЭШЕЛОН: N. Сложные задачи отложи в очередь до возврата эшелона 1, механические делай сразу."
                    Set-Content $status ("СОСТОЯНИЕ: РАБОТАЮ`r`nЭШЕЛОН: 2-3`r`nОБНОВЛЕНО: " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + "`r`nЗАДАЧА: продолжение на эшелоне 2-3 после лимита эшелона 1")
                } else {
                    $reset = Get-Date -Hour ([int]$Matches[1]) -Minute ([int]$Matches[2]) -Second 0
                    if ($reset -lt (Get-Date)) { $reset = $reset.AddDays(1) }
                    $reset = $reset.AddMinutes(5)
                    Log "лимит, внизу пусто; жду до $($reset.ToString('HH:mm'))"
                    while ((Get-Date) -lt $reset) { Start-Sleep 60 }
                    Zapustit "Ты слон. Ты молчал из-за лимита, он сбросился. Продолжай работу по правилам моста из most/README.md: прочитай most/status.md и очередь most/ochered-komand.txt."
                    Set-Content $status ("СОСТОЯНИЕ: РАБОТАЮ`r`nОБНОВЛЕНО: " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + "`r`nЗАДАЧА: продолжение после перезапуска стражем")
                }
            }
        }

        # 4. Завис: сердце молчит дольше 40 минут, но Strix/полигоны — не молчание
        if ((SerdceStale 40) -and -not (RobotyBezAgenta)) {
            Log "сердце молчит 40 минут; перезапуск"
            Get-Process opencode* -ErrorAction SilentlyContinue | Stop-Process -Force
            Zapustit "Ты слон. Ты молчал сорок минут. Прочитай most/status.md, восстанови картину и продолжай последнюю задачу по правилам моста из most/README.md."
            Set-Content $serdce "restart"
        }

        # 5. Агент не запущен, а команда ждёт
        if ((-not (OpenCodeZhiv)) -and (Test-Path $ochered) -and ((Get-Item $ochered).Length -gt 0)) {
            Zapustit "Ты слон. Прочитай most/README.md и очередь most/ochered-komand.txt: там команда от человека. Выполни по правилам моста."
        }
    }
    catch { Log "ошибка стража: $($_.Exception.Message)" }
    Start-Sleep 60
}
