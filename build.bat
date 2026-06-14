@echo off
setlocal

REM ---- Config ----
set PY=python
set PI=%PY% -m PyInstaller

REM ---- Target dispatcher ----
if "%1"=="" goto all
if "%1"=="all" goto all
if "%1"=="init" goto init
if "%1"=="complete" goto complete
if "%1"=="server-init" goto server_init
if "%1"=="server-all" goto server_all
if "%1"=="server" goto server
if "%1"=="client-init" goto client_init
if "%1"=="client-all" goto client_all
if "%1"=="client" goto client
if "%1"=="clean" goto clean

echo Unknown target: %1
goto end

REM ---- Targets ----

:all
call "%~f0" server
call "%~f0" client
goto end

:init
call "%~f0" server-init
call "%~f0" client-init
goto end

:complete
call "%~f0" init
call "%~f0" all
goto end

:server_all
call "%~f0" server-init
goto server

:server_init
echo === Building server (init) ===
%PI% --onefile --windowed --name "server" --icon "server.ico" --additional-hooks-dir "pyinstaller_hooks" --add-data "cfg;cfg" --add-data "assets;assets" --add-data "common/room_templates;common/room_templates" server.py
goto end

:server
echo === Building server (spec) ===
%PI% server.spec
goto end

:client_all
call "%~f0" client-init
goto client

:client_init
echo === Building client (init) ===
%PI% --onefile --windowed --name "gui_client" --icon "client.ico" --additional-hooks-dir "pyinstaller_hooks" --add-data "cfg;cfg" --add-data "assets;assets" gui_client.py
goto end

:client
echo === Building client (spec) ===
%PI% gui_client.spec
goto end

:clean
echo === Cleaning build artifacts ===
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
goto end

:end
endlocal
