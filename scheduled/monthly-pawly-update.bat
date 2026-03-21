@echo off
cd /d "C:\Users\user\Desktop\work\seo-tools\seo-blog-engine"
echo [%date% %time%] Starting monthly UPDATE for Pawly >> "scheduled\logs\pawly-update.log"
python -u run.py update --config config.pawly.yaml >> "scheduled\logs\pawly-update.log" 2>&1
echo [%date% %time%] Finished >> "scheduled\logs\pawly-update.log"
