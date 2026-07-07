@echo off
REM One-click daily (manual): tag new images + immich import, then enqueue new no-character images to Tier 0.
REM Edit ROOT below to your install path.
chcp 65001 >nul
set ROOT=D:\Software\ImageTagger
cd /d %ROOT%
set PY=%ROOT%\venv_camie\Scripts\python.exe

echo [1/2] camie tagging (recent) + immich import
"%PY%" camie_pipeline.py recent

echo [2/2] enqueue new no-character images to Tier 0
"%PY%" enqueue_tier0.py

echo Done.
pause
