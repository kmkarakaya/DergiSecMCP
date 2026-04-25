@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SPACE_REPO=https://huggingface.co/spaces/kmkarakaya/derrgitarama"
set "SPACE_DIR=C:\Codes\derrgitarama-space"
set "COMMIT_MESSAGE=Deploy DergiSec to HF Space"
set "SOURCE_DIR=%~dp0"
set "WORK_DIR="
set "DRY_RUN=0"

if /I "%~1"=="/help" goto :help
if /I "%~1"=="-h" goto :help
if /I "%~1"=="--help" goto :help

if /I "%~1"=="/dry-run" (
    set "DRY_RUN=1"
    shift
)

if not "%~1"=="" set "SPACE_REPO=%~1"
if not "%~2"=="" set "SPACE_DIR=%~2"
if not "%~3"=="" set "COMMIT_MESSAGE=%~3"

if "%SOURCE_DIR:~-1%"=="\" set "SOURCE_DIR=%SOURCE_DIR:~0,-1%"

echo [1/6] Checking required tools...
where git >nul 2>nul || (
    echo ERROR: git not found in PATH.
    exit /b 1
)
where robocopy >nul 2>nul || (
    echo ERROR: robocopy not found in PATH.
    exit /b 1
)

echo Source repo : %SOURCE_DIR%
echo HF Space    : %SPACE_REPO%
echo Target dir  : %SPACE_DIR%
echo Commit msg  : %COMMIT_MESSAGE%

if "%DRY_RUN%"=="1" (
    echo.
    echo Dry run enabled. No files will be copied or pushed.
    exit /b 0
)

echo.
echo [2/6] Preparing local HF Space clone...
set "WORK_DIR=%SPACE_DIR%"
if exist "%SPACE_DIR%\.git" (
    for /f "delims=" %%I in ('git -C "%SPACE_DIR%" remote get-url origin 2^>nul') do set "CURRENT_REMOTE=%%I"
    if not defined CURRENT_REMOTE (
        echo ERROR: %SPACE_DIR% exists but is not a valid git repository.
        exit /b 1
    )
    if /I not "!CURRENT_REMOTE!"=="%SPACE_REPO%" (
        echo ERROR: Existing repository remote does not match target Space.
        echo Found  : !CURRENT_REMOTE!
        echo Expect : %SPACE_REPO%
        exit /b 1
    )
) else if exist "%SPACE_DIR%\*" (
    set "WORK_DIR=%TEMP%\hf-space-%RANDOM%%RANDOM%"
    echo Target directory exists without git metadata. Using temporary clone workspace:
    echo !WORK_DIR!
    git clone "%SPACE_REPO%" "!WORK_DIR!" || exit /b 1
) else (
    echo Cloning Space repository...
    git clone "%SPACE_REPO%" "%SPACE_DIR%" || exit /b 1
)

echo.
echo [3/6] Syncing files to Space working tree...
robocopy "%SOURCE_DIR%" "%WORK_DIR%" /E /XD .git .venv __pycache__ .pytest_cache .mypy_cache .vscode node_modules .playwright-mcp /XF "~$*.xlsx"
set "ROBOCOPY_EXIT=%ERRORLEVEL%"
if %ROBOCOPY_EXIT% GEQ 8 (
    echo ERROR: robocopy failed with exit code %ROBOCOPY_EXIT%.
    if /I not "%WORK_DIR%"=="%SPACE_DIR%" rmdir /S /Q "%WORK_DIR%" 2>nul
    exit /b %ROBOCOPY_EXIT%
)

del /Q "%WORK_DIR%\~$*.xlsx" 2>nul

echo.
echo [4/6] Checking for changes...
pushd "%WORK_DIR%" || exit /b 1
set "HAS_CHANGES=0"
for /f "delims=" %%I in ('git status --porcelain') do (
    set "HAS_CHANGES=1"
    goto :changes_found
)

:changes_found
if "%HAS_CHANGES%"=="0" (
    echo No changes detected. Nothing to commit.
    popd
    if /I not "%WORK_DIR%"=="%SPACE_DIR%" rmdir /S /Q "%WORK_DIR%" 2>nul
    exit /b 0
)

echo.
echo [5/6] Creating commit...
git add . || (
    popd
    if /I not "%WORK_DIR%"=="%SPACE_DIR%" rmdir /S /Q "%WORK_DIR%" 2>nul
    exit /b 1
)
git commit -m "%COMMIT_MESSAGE%" || (
    echo ERROR: git commit failed.
    popd
    if /I not "%WORK_DIR%"=="%SPACE_DIR%" rmdir /S /Q "%WORK_DIR%" 2>nul
    exit /b 1
)

echo.
echo [6/6] Pushing to Hugging Face Space...
git push origin HEAD || (
    echo ERROR: git push failed.
    popd
    if /I not "%WORK_DIR%"=="%SPACE_DIR%" rmdir /S /Q "%WORK_DIR%" 2>nul
    exit /b 1
)

popd
if /I not "%WORK_DIR%"=="%SPACE_DIR%" rmdir /S /Q "%WORK_DIR%" 2>nul
echo.
echo Done. Check build logs at:
echo %SPACE_REPO%
exit /b 0

:help
echo Usage:
echo   push_hf_space.bat [/dry-run] [space_repo] [space_dir] [commit_message]
echo.
echo Examples:
echo   push_hf_space.bat
echo   push_hf_space.bat /dry-run
echo   push_hf_space.bat https://huggingface.co/spaces/kmkarakaya/derrgitarama C:\Codes\derrgitarama-space "Deploy latest app"
exit /b 0