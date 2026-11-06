@echo off
REM Launch run_local.ps1 via PowerShell (handles spaces in path reliably)
powershell -ExecutionPolicy Bypass -File "%~dp0run_local.ps1"
