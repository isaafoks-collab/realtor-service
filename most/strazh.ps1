# strazh.ps1 — страж моста «слон и рыбки» (realtor-service)
# Живёт в фоне, раз в минуту: собирает команды из GitHub, ловит лимит, перезапускает агента,
# следит за эшелонами каскада (freellmapi/OmniRoute/Ollama) и поднимает умершие.
# Версия 2 (2026-11-16): работающий агент НЕ убивается по таймеру молчания —
# живость проверяется по CPU всего дерева процессов агента; убиваются только
# реально висящие (5 минут нулевой активности); перезапуски с бэкоффом; status.md стражем не затирается.
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
function AgentProcs {
    return @(Get-Process opencode* -ErrorAction SilentlyContinue)
}
function AgentZhiv {
    return ((AgentProcs).Count -gt 0)
}
# CPU всего дерева процессов агента (opencode + его дети-тулзы: python/node/...)
function AgentCpuTicks {
    $all = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue
    if (-not $all) { return $null }
    $ids = New-Object System.Collections.Generic.HashSet[uint32]
    foreach ($pr in $all) {
        if ($pr.Name -like "opencode*") { [void]$ids.Add([uint32]$pr.ProcessId) }
    }
    $changed = $true
    while ($changed) {
        $changed = $false
        foreach ($pr in $all) {
            if ($ids.Contains([uint32]$pr.ParentProcessId) -and -not $ids.Contains([uint32]$pr.ProcessId)) {
                [void]$ids.Add([uint32]$pr.ProcessId); $changed = $true
            }
        }
    }
    $sum = 0
    foreach ($p in (Get-Process -ErrorAction SilentlyContinue)) {
        if ($ids.Contains([uint32]$p.Id)) { try { $sum += $p.TotalProcessorTime.Ticks } catch {} }
    }
    return $sum
}
function Zapustit($prompt) {
    Log "запуск OpenCode: $prompt"
    $cmd = "cd /d '$proj' && opencode run -c --auto `"$prompt`""
    Start-Process cmd.exe -ArgumentList "/c", $cmd -WindowStyle Hidden
    Set-Content $serdce "restart"
    $script:lastLaunch = Get-Date
    $script:cpuSnap = $null
    $script:idleStreak = 0
    $script:deathCounted = $false
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

# --- состояние цикла ---
$script:lastLaunch    = (Get-Date).AddMinutes(-60)
$script:lastEshSwitch = (Get-Date).AddMinutes(-60)
$script:cpuSnap       = $null
$script:idleStreak    = 0
$script:quickExits    = 0
$script:deathCounted  = $false

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

        # 3. Живость агента по CPU дерева процессов: работает — трогаем сердце, НЕ убиваем
        $ticks = AgentCpuTicks
        if (AgentZhiv) {
            if ($null -ne $ticks -and $null -ne $script:cpuSnap -and ($ticks - $script:cpuSnap) -gt 10000000) {
                # больше 1 сек CPU за минуту по дереву — агент работает
                Set-Content $serdce "tick"
                $script:idleStreak = 0
            } else {
                $script:idleStreak++
            }
            $script:cpuSnap = $ticks
        } else {
            $script:cpuSnap = $null
            $script:idleStreak = 0
        }

        # 3b. Быстрая смерть после запуска (пустой бакет/сбой) — растим бэкофф,
        #     чтобы не долбить по мёртвому эшелону каждые 40 минут
        if (-not (AgentZhiv) -and -not $script:deathCounted -and ((Get-Date) - $script:lastLaunch).TotalMinutes -lt 10) {
            $script:quickExits = [Math]::Min($script:quickExits + 1, 4)
            $script:deathCounted = $true
            Log ("агент умер сразу после запуска — бэкофф, следующий запуск через {0} мин" -f [Math]::Min(40 + 20 * $script:quickExits, 120))
        }

        # 4. Лимит: агент сам остановился (не запущен) — переключаем эшелон или ждём сброса
        if (Test-Path $status) {
            $st = Get-Content $status -Raw
            if ($st -match "СОСТОЯНИЕ:\s*ЖДУ ЛИМИТ" -and -not (AgentZhiv)) {
                $niz = (OmniZhiv -or FreellmZhiv -or OllamaZhiv)
                if ($niz -and ((Get-Date) - $script:lastEshSwitch).TotalMinutes -gt 45) {
                    Log "лимит эшелона 1, внизу есть топливо — переключение на эшелон 2-3 (пауза между попытками 45 мин)"
                    $script:lastEshSwitch = Get-Date
                    Zapustit "Ты слон. Лимит эшелона 1 сбрасывается позже. Внизу есть топливо: freellmapi (127.0.0.1:3001) и OmniRoute (127.0.0.1:20128) живы, Ollama (127.0.0.1:11434, qwen2.5-coder:3b) — дно. Продолжай работу на эшелоне 2 или 3, записав в most/status.md строку ЭШЕЛОН: N и состояние РАБОТАЮ. Сложные задачи отложи в очередь до возврата эшелона 1, механические делай сразу."
                    Start-Sleep 20
                } elseif (-not $niz -and $st -match "СБРОС:\s*(\d{1,2}):(\d{2})") {
                    $reset = Get-Date -Hour ([int]$Matches[1]) -Minute ([int]$Matches[2]) -Second 0
                    if ($reset -lt (Get-Date)) { $reset = $reset.AddDays(1) }
                    $reset = $reset.AddMinutes(5)
                    Log "лимит, внизу пусто; жду до $($reset.ToString('HH:mm'))"
                    while ((Get-Date) -lt $reset) { Start-Sleep 60 }
                    Zapustit "Ты слон. Ты молчал из-за лимита, он сбросился. Продолжай работу по правилам моста из most/README.md: прочитай most/status.md и очередь most/ochered-komand.txt."
                } elseif (-not $niz) {
                    Log "лимит, внизу пусто, время сброса неизвестно — проверю через 15 минут"
                    Start-Sleep 900
                }
                # агент запущен и работает — не трогаем: он сам разберётся с лимитом
            }
        }

        # 5. Молчание сердца: убиваем ТОЛЬКО висящего агента или запускаем отсутствующего
        if ((SerdceStale 40) -and -not (RobotyBezAgenta)) {
            $staleLimit = [Math]::Min(40 + 20 * $script:quickExits, 120)
            if ((SerdceStale $staleLimit) -and -not (AgentZhiv)) {
                if (((Get-Date) - $script:lastLaunch).TotalMinutes -lt 15) { $script:quickExits++ } else { $script:quickExits = 0 }
                Log "сердце молчит $staleLimit мин, агент не запущен — запуск (быстрых падений подряд: $($script:quickExits))"
                Zapustit "Ты слон. Ты молчал сорок минут. Прочитай most/status.md, восстанови картину и продолжай последнюю задачу по правилам моста из most/README.md. Если упёрся в лимит — запиши СОСТОЯНИЕ: ЖДУ ЛИМИТ и строку СБРОС: ЧЧ:ММ."
            } elseif ((SerdceStale $staleLimit) -and $script:idleStreak -ge 5) {
                Log "агент запущен, но без активности $($script:idleStreak) мин и сердце молчит $staleLimit мин — висит, перезапуск"
                (AgentProcs) | Stop-Process -Force
                Start-Sleep 3
                Zapustit "Ты слон. Ты молчал сорок минут. Прочитай most/status.md, восстанови картину и продолжай последнюю задачу по правилам моста из most/README.md. Если упёрся в лимит — запиши СОСТОЯНИЕ: ЖДУ ЛИМИТ и строку СБРОС: ЧЧ:ММ."
            }
            # иначе: агент жив и работает (CPU-проверка уже тронула сердце) — не убиваем
        }
    }
    catch { Log "ошибка стража: $($_.Exception.Message)" }
    Start-Sleep 60
}
