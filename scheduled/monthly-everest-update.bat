@echo off
cd /d "C:\Users\user\Desktop\work\seo-tools\seo-blog-engine"
echo [%date% %time%] Starting monthly UPDATE for Everest >> "scheduled\logs\everest-update.log"
python -u run.py update --config config.everst.yaml >> "scheduled\logs\everest-update.log" 2>&1
echo [%date% %time%] Finished >> "scheduled\logs\everest-update.log"
