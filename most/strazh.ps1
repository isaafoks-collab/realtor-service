# strazh.ps1 — страж моста «слон и рыбки» (realtor-service)
# Живёт в фоне, раз в минуту: собирает команды из GitHub, ловит лимит, перезапускает агента
$ErrorActionPreference = "Continue"

$proj    = "C:\Users\Андрей\Documents\realtor-service"
$most    = Join-Path $proj "most"
$status  = Join-Path $most "status.md"
$serdce  = Join-Path $most "serdce.txt"
$ochered = Join-Path $most "ochered-komand.txt"
$log     = Join-Path $most "strazh-log.txt"
$repo    = "isaafoks-collab/realtor-most"      # публичный репо-почта (https://github.com/isaafoks-collab/realtor-most)

function Log($m) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $m" | Add-Content $log }

# один экземпляр стража
$mutex = New-Object System.Threading.Mutex($false, "Global\strazh-realtor")
if (-not $mutex.WaitOne(0)) { exit }

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

        # 2. Лимит: агент записал время сброса — страж ждёт и запускает
        if (Test-Path $status) {
            $st = Get-Content $status -Raw
            if ($st -match "СОСТОЯНИЕ:\s*ЖДУ ЛИМИТ" -and $st -match "СБРОС:\s*(\d{1,2}):(\d{2})") {
                $reset = Get-Date -Hour ([int]$Matches[1]) -Minute ([int]$Matches[2]) -Second 0
                if ($reset -lt (Get-Date)) { $reset = $reset.AddDays(1) }
                $reset = $reset.AddMinutes(5)
                Log "лимит; жду до $($reset.ToString('HH:mm'))"
                while ((Get-Date) -lt $reset) { Start-Sleep 60 }
                Zapustit "Ты слон. Ты молчал из-за лимита, он сбросился. Продолжай работу по правилам моста из most/README.md: прочитай most/status.md и очередь most/ochered-komand.txt."
                Set-Content $status ("СОСТОЯНИЕ: РАБОТАЮ`r`nОБНОВЛЕНО: " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + "`r`nЗАДАЧА: продолжение после перезапуска стражем")
            }
        }

        # 3. Завис: сердце молчит дольше 40 минут
        if (SerdceStale 40) {
            Log "сердце молчит 40 минут; перезапуск"
            Get-Process opencode* -ErrorAction SilentlyContinue | Stop-Process -Force
            Zapustit "Ты слон. Ты молчал сорок минут. Прочитай most/status.md, восстанови картину и продолжай последнюю задачу по правилам моста из most/README.md."
            Set-Content $serdce "restart"
        }

        # 4. Агент не запущен, а команда ждёт
        if ((-not (OpenCodeZhiv)) -and (Test-Path $ochered) -and ((Get-Item $ochered).Length -gt 0)) {
            Zapustit "Ты слон. Прочитай most/README.md и очередь most/ochered-komand.txt: там команда от человека. Выполни по правилам моста."
        }
    }
    catch { Log "ошибка стража: $($_.Exception.Message)" }
    Start-Sleep 60
}
