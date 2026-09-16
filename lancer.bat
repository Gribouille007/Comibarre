@echo off
rem Lance le logiciel sur Windows, par un double-clic dans l'explorateur.
rem
rem Ce fichier cherche un Python assez recent, propose de l'installer s'il n'y
rem en a pas, puis passe la main a demarrer.py, qui installe les bibliotheques
rem et ouvre la fenetre.

setlocal
cd /d "%~dp0"

set PYTHON=

rem Le lanceur « py » est installe avec Python sous Windows et sait choisir la
rem bonne version. On lui demande la plus recente, puis on verifie qu'elle est
rem assez recente pour ce logiciel.
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 set PYTHON=py -3

if defined PYTHON goto lancer

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 set PYTHON=python

if defined PYTHON goto lancer
goto installer

:installer
echo.
echo Aucun Python 3.11 ou plus recent n'a ete trouve sur cet ordinateur.
echo.

where winget >nul 2>&1
if errorlevel 1 goto telecharger

set /p REPONSE="Installer Python maintenant via winget ? [o/N] "
if /i not "%REPONSE%"=="o" goto telecharger

winget install --exact --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
if errorlevel 1 goto telecharger

echo.
echo Python vient d'etre installe. Fermez cette fenetre, puis relancez
echo « lancer.bat » : Windows doit d'abord prendre en compte l'installation.
pause
exit /b 1

:telecharger
echo Telechargez Python depuis https://www.python.org/downloads/
echo Pensez a cocher « Add python.exe to PATH » pendant l'installation.
start "" "https://www.python.org/downloads/"
pause
exit /b 1

:lancer
%PYTHON% demarrer.py %*
if errorlevel 1 pause
endlocal
