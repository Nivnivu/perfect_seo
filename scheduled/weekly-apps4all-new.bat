@echo off
cd /d "C:\Users\user\Desktop\work\seo-tools\seo-blog-engine"
echo [%date% %time%] Starting weekly NEW post for Apps4All >> "scheduled\logs\apps4all-new.log"
python -u run.py new --config config.apps4all.yaml >> "scheduled\logs\apps4all-new.log" 2>&1
echo [%date% %time%] Finished >> "scheduled\logs\apps4all-new.log"
