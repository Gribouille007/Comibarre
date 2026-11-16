@echo off
rem Lance le logiciel sur Windows, par un double-clic dans l'explorateur.
rem
rem Ce fichier cherche un Python assez recent, propose de l'installer s'il n'y
rem en a pas, puis passe la main a demarrer.py, qui installe les bibliotheques
rem et ouvre la fenetre.

setlocal
cd /d "%~dp0"

rem Lancement rapide : une fois l'installation faite, le Python de
rem l'environnement isole ouvre directement le logiciel, sans chercher un
rem Python a chaque lancement. demarrer.py repond 3 quand il y a quelque chose
rem a installer ou a reparer, et un Python qui ne demarre plus donne un autre
rem code que 0 ou 1 : dans ces cas seulement, on continue par le chemin complet.
if not "%~1"=="" goto chercher
if not exist "venv\Scripts\python.exe" goto chercher
set LANCEUR_FAIT_UNE_PAUSE=1
"venv\Scripts\python.exe" demarrer.py
if "%errorlevel%"=="0" goto fin
if "%errorlevel%"=="1" goto erreur

:chercher
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
echo "lancer.bat" : Windows doit d'abord prendre en compte l'installation.
pause
exit /b 1

:telecharger
echo Telechargez Python depuis https://www.python.org/downloads/
echo Pensez a cocher "Add python.exe to PATH" pendant l'installation.
start "" "https://www.python.org/downloads/"
pause
exit /b 1

:lancer
rem demarrer.py ne fait pas sa propre pause : celle d'ici suffit.
set LANCEUR_FAIT_UNE_PAUSE=1
%PYTHON% demarrer.py %*
rem "if errorlevel 1" ne voit pas les codes negatifs : un plantage de Python
rem sous Windows (0xC0000005) en donne un, et la fenetre se fermait sans pause.
if not "%errorlevel%"=="0" goto erreur
goto fin

:erreur
pause

:fin
endlocal
