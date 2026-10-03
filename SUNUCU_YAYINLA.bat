@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo HOLO sunucu guncelleniyor...
set LOG=%~dp0deploy_log.txt
echo --- %date% %time% > "%LOG%"
where supabase >nul 2>nul
if %errorlevel%==0 (set SB=supabase) else (set SB=npx -y supabase)
call %SB% functions deploy scores --no-verify-jwt --project-ref btpiblrrsjmhuacwkopr --use-api >> "%LOG%" 2>&1
if errorlevel 1 (
  echo --use-api olmadan tekrar deneniyor >> "%LOG%"
  call %SB% functions deploy scores --no-verify-jwt --project-ref btpiblrrsjmhuacwkopr >> "%LOG%" 2>&1
)
echo EXIT %errorlevel% >> "%LOG%"
type "%LOG%"
echo.
echo Bitti. Bu pencereyi kapatabilirsin.
pause
