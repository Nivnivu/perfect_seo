@echo off
cd /d "C:\Users\user\Desktop\work\seo-tools\seo-blog-engine"
echo [%date% %time%] Starting monthly UPDATE for Apps4All >> "scheduled\logs\apps4all-update.log"
python -u run.py update --config config.apps4all.yaml >> "scheduled\logs\apps4all-update.log" 2>&1
echo [%date% %time%] Finished >> "scheduled\logs\apps4all-update.log"
