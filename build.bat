@echo off
setlocal

REM ---- Config ----
set PY=python
set PI=%PY% -m PyInstaller

REM ---- Target dispatcher ----
if "%1"=="" goto all
if "%1"=="all" goto all
if "%1"=="init" goto init
if "%1"=="server-init" goto server_init
if "%1"=="server" goto server
if "%1"=="client-init" goto client_init
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

:server_init
echo === Building server (init) ===
%PI% --onefile --name "test_server" --add-data "cfg;cfg" test_server.py
goto end

:server
echo === Building server (spec) ===
%PI% test_server.spec
goto end

:client_init
echo === Building client (init) ===
%PI% --onefile --name "test_client" --add-data "cfg;cfg" test_client.py
goto end

:client
echo === Building client (spec) ===
%PI% test_client.spec
goto end

:clean
echo === Cleaning build artifacts ===
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
goto end

:end
endlocal
