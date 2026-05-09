@echo off
echo Running flashix bootstrap (Windows)
where node >nul 2>&1 || (echo node not found & exit /b 1)
where python >nul 2>&1 || (echo python not found & exit /b 1)
python -m venv venv
call venv\Scripts\activate
pip install -r requirements.txt
npm install
mkdir data\logs
if not exist .env.local copy .env.example .env.local
echo Bootstrap complete. Edit .env.local to add credentials.
