@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo  MonitorPing - Build Windows corrigido
echo ========================================

if not exist .venv (
    echo Criando ambiente virtual...
    py -3 -m venv .venv
    if errorlevel 1 python -m venv .venv
)
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERRO: nao foi possivel ativar o ambiente virtual.
    pause
    exit /b 1
)

python -m pip install --upgrade pip wheel
if errorlevel 1 goto :erro

REM pygame-ce fornece o modulo pygame, mas possui wheels pre-compilados.
REM --only-binary impede que o pip tente compilar pygame localmente.
python -m pip install --upgrade --only-binary=:all: pygame-ce pystray Pillow win10toast winotify pyinstaller
if errorlevel 1 goto :erro

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

python -m PyInstaller --clean --noconfirm --windowed --onedir ^
  --name MonitorPing ^
  --noupx ^
  --hidden-import=win10toast ^
  --hidden-import=pystray._win32 ^
  --add-data "ips.json;." ^
  monitorping.py
if errorlevel 1 goto :erro

if not exist dist\MonitorPing\MonitorPing.exe goto :erro
copy /y ips.json dist\MonitorPing\ips.json >nul

echo.
echo BUILD CONCLUIDO COM SUCESSO!
echo Executavel: %CD%\dist\MonitorPing\MonitorPing.exe
echo.
pause
endlocal
exit /b 0

:erro
echo.
echo ERRO: o build falhou.
echo Verifique a mensagem acima.
pause
endlocal
exit /b 1
