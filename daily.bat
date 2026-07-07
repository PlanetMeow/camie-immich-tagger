@echo off
REM Unattended daily (Task Scheduler): recent tag + enqueue + Tier 0 consume. Edit ROOT below.
chcp 65001 >nul
set ROOT=D:\Software\ImageTagger
cd /d %ROOT%
set PY=%ROOT%\venv_camie\Scripts\python.exe

echo [%date% %time%] daily start
"%PY%" camie_pipeline.py recent
"%PY%" enqueue_tier0.py
"%PY%" tier0_saucenao.py
echo [%date% %time%] daily done
