@echo off
REM ============================================================
REM  Unattended daily run for Windows Task Scheduler. Edit ROOT below.
REM  Suggested triggers (see README):
REM    trigger 1: at logon + 5 min delay
REM    trigger 2: every day 00:05 (StartWhenAvailable = catch up if missed)
REM  Runs at most once per calendar day (stamp: daily_last_run.txt).
REM  The stamp is written only after ALL steps finish, so a run that is
REM  interrupted (window closed, shutdown) is retried on the next trigger.
REM  Before running, wait_deps.py waits (up to 20 min) for immich (Docker)
REM  and, if Tier 0 is configured, network access to SauceNAO;
REM  if not ready, exit without stamp.
REM  Use "daily.bat force" to bypass the once-per-day guard.
REM  Output is shown in this window AND appended to daily.log (tee_run.py);
REM  daily.log is rotated to daily.log.old when larger than 5 MB.
REM  Steps:
REM    1) camie tag recent new images + immich import
REM    2) enqueue new no-character images into Tier 0 queue
REM    3) Tier 0 SauceNAO consume queue (rate-limited)
REM  No pause (unattended). ASCII-only comments (non-ASCII can be
REM  mis-decoded by cmd and crash the script).
REM  No parenthesized if-blocks around echo text (cmd parsing pitfalls).
REM ============================================================
chcp 65001 >nul
title ImageTagger daily - running, do not close (log: daily.log)
set ROOT=D:\Software\ImageTagger
cd /d %ROOT%
set PY=%ROOT%\venv_camie\Scripts\python.exe
set STAMP=%ROOT%\daily_last_run.txt
set LOG=%ROOT%\daily.log
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
set TEE="%PY%" tee_run.py "%LOG%"

if exist "%LOG%" for %%A in ("%LOG%") do if %%~zA GTR 5000000 move /y "%LOG%" "%LOG%.old" >nul

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set TODAY=%%i
set LAST=
if exist "%STAMP%" set /p LAST=<"%STAMP%"
if /i "%~1"=="force" goto run
if not "%LAST%"=="%TODAY%" goto run
call :log [%date% %time%] already ran today %TODAY%, skip.
exit /b 0

:run
echo.
>>"%LOG%" echo.
call :log [%date% %time%] ===== daily start %~1 =====
call :log ImageTagger daily is running. Do not close this window. Full log: %LOG%

%TEE% "%PY%" wait_deps.py
if not errorlevel 1 goto deps_ok
call :log [%date% %time%] ===== deps not ready, abort, stamp NOT written =====
exit /b 1

:deps_ok
call :log [1/3] camie tagging recent + immich import
%TEE% "%PY%" camie_pipeline.py recent

call :log [2/3] enqueue new no-character images
%TEE% "%PY%" enqueue_tier0.py

call :log [3/3] Tier 0 SauceNAO, consume queue, rate-limited
%TEE% "%PY%" tier0_saucenao.py

>"%STAMP%" echo %TODAY%
call :log [%date% %time%] ===== daily done, stamp written %TODAY% =====
exit /b 0

:log
echo %*
>>"%LOG%" echo %*
exit /b 0
