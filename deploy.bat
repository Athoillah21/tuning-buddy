@echo off
title Tuning Buddy - Deployment
color 0b

echo.
echo ==============================================
echo   Tuning Buddy - Deployment Script
echo ==============================================
echo.

:: Check status
git status --short

echo.
set /p commitMsg="Enter deployment message (default: 'Update deployment'): "
if "%commitMsg%"=="" set commitMsg=Update deployment

echo.
echo [1/3] Adding files...
git add .

echo [2/3] Committing changes...
git commit -m "%commitMsg%"

echo [3/3] Pushing to GitHub...
git push origin main

echo.
if %ERRORLEVEL% EQU 0 (
    color 0a
    echo [SUCCESS] Deployed successfully! 
    echo Vercel will auto-deploy in 2-3 minutes.
) else (
    color 0c
    echo [ERROR] Something went wrong.
)

echo.
pause
