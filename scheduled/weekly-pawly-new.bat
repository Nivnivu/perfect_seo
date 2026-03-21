@echo off
cd /d "C:\Users\user\Desktop\work\seo-tools\seo-blog-engine"
echo [%date% %time%] Starting weekly NEW post for Pawly >> "scheduled\logs\pawly-new.log"
python -u run.py new --config config.pawly.yaml >> "scheduled\logs\pawly-new.log" 2>&1
echo [%date% %time%] Finished >> "scheduled\logs\pawly-new.log"
