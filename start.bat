@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ====================================
echo  N 블로그 자동화 웹앱 시작
echo ====================================
pip install -r requirements.txt -q
python -X utf8 app.py
pause
