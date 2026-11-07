@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ===== ZAS OneBrain =====
where python >nul 2>nul || (echo لازم تنزل Python من python.org الأول & pause & exit /b 1)
if not exist .venv (
  echo اول مرة: بنجهز البرنامج... ممكن ياخد دقيقة
  python -m venv .venv
  .venv\Scripts\python -m pip install -q -r requirements.txt
)
start "" http://127.0.0.1:8000
.venv\Scripts\python -m uvicorn onebrain.main:create_app --factory --port 8000
pause
