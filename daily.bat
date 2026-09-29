@echo off
REM ============================================================
REM  Unattended daily run for Windows Task Scheduler. Edit ROOT below.
REM  Suggested triggers (see README): at logon + 5 min delay, and daily 00:05,
REM  with "Start when available" enabled.
REM  Runs at most once per calendar day (stamp: daily_last_run.txt),
REM  so multiple triggers never double-run.
REM  Before running, wait_deps.py waits (up to 20 min) for immich and,
REM  if Tier 0 is configured, network access to SauceNAO. If they are not
REM  ready, exit WITHOUT writing the stamp so the next trigger retries.
REM  Use "daily.bat force" to bypass the once-per-day guard.
REM  All output (incl. skips) is appended to daily.log;
REM  daily.log is rotated to daily.log.old when larger than 5 MB.
REM  Steps:
REM    1) camie tag recent new images + immich import
REM    2) enqueue new no-character images into Tier 0 queue
REM    3) Tier 0 SauceNAO consume queue (rate-limited)
REM  ASCII-only comments (non-ASCII can be mis-decoded by cmd and crash).
REM ============================================================
chcp 65001 >nul
set ROOT=D:\Software\ImageTagger
cd /d %ROOT%
set PY=%ROOT%\venv_camie\Scripts\python.exe
set STAMP=%ROOT%\daily_last_run.txt
set LOG=%ROOT%\daily.log
set PYTHONIOENCODING=utf-8

if exist "%LOG%" for %%A in ("%LOG%") do if %%~zA GTR 5000000 move /y "%LOG%" "%LOG%.old" >nul

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set TODAY=%%i
set LAST=
if exist "%STAMP%" set /p LAST=<"%STAMP%"
if /i "%~1"=="force" goto run
if "%LAST%"=="%TODAY%" (
    >>"%LOG%" echo [%date% %time%] already ran today (%TODAY%^), skip.
    exit /b 0
)

:run
>>"%LOG%" echo.
>>"%LOG%" echo [%date% %time%] ===== daily start (%~1) =====

"%PY%" wait_deps.py >>"%LOG%" 2>&1
if errorlevel 1 (
    >>"%LOG%" echo [%date% %time%] ===== deps not ready, abort, stamp NOT written =====
    exit /b 1
)
>"%STAMP%" echo %TODAY%

>>"%LOG%" echo [1/3] camie tagging (recent) + immich import
"%PY%" camie_pipeline.py recent >>"%LOG%" 2>&1

>>"%LOG%" echo [2/3] enqueue new no-character images
"%PY%" enqueue_tier0.py >>"%LOG%" 2>&1

>>"%LOG%" echo [3/3] Tier 0 SauceNAO (consume queue, rate-limited)
"%PY%" tier0_saucenao.py >>"%LOG%" 2>&1

>>"%LOG%" echo [%date% %time%] ===== daily done =====
