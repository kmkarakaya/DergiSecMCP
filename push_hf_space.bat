@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SPACE_REPO=https://huggingface.co/spaces/kmkarakaya/dergitarama"
set "SPACE_DIR=C:\Codes\dergitarama-space"
set "COMMIT_MESSAGE=Deploy DergiSec to HF Space"
set "SOURCE_DIR=%~dp0"
set "WORK_DIR="
set "DRY_RUN=0"
set "SKIP_DOCKER_CHECK=0"
set "GIT_XET_PATH=C:\Program Files\Git-Xet"
set "DOCKER_TAG=derrgisec-hf-preflight"

if "%SOURCE_DIR:~-1%"=="\" set "SOURCE_DIR=%SOURCE_DIR:~0,-1%"

if exist "%GIT_XET_PATH%\git-xet.exe" set "PATH=%GIT_XET_PATH%;%PATH%"

set "POSITIONAL_INDEX=0"

:parse_args
if "%~1"=="" goto :args_done
if /I "%~1"=="/help" goto :help
if /I "%~1"=="-h" goto :help
if /I "%~1"=="--help" goto :help
if /I "%~1"=="/dry-run" (
    set "DRY_RUN=1"
    shift
    goto :parse_args
)
if /I "%~1"=="/skip-docker-check" (
    set "SKIP_DOCKER_CHECK=1"
    shift
    goto :parse_args
)

set /a POSITIONAL_INDEX+=1
if %POSITIONAL_INDEX%==1 set "SPACE_REPO=%~1"
if %POSITIONAL_INDEX%==2 set "SPACE_DIR=%~1"
if %POSITIONAL_INDEX%==3 set "COMMIT_MESSAGE=%~1"
shift
goto :parse_args

:args_done

echo [1/7] Checking required tools and files...
where git >nul 2>nul || (
    echo ERROR: git not found in PATH.
    exit /b 1
)
where robocopy >nul 2>nul || (
    echo ERROR: robocopy not found in PATH.
    exit /b 1
)
git xet --version >nul 2>nul || (
    echo ERROR: git-xet is not installed.
    echo.
    echo Hugging Face rejected the Excel files because binary files must be pushed through Xet storage.
    echo Install it on Windows with one of these options:
    echo   winget install git-xet
    echo   or install the MSI from the git-xet Windows release page
    echo.
    echo Then run:
    echo   "C:\Program Files\Git-Xet\git-xet.exe" install
    echo.
    echo After that, rerun this script.
    exit /b 1
)

for %%F in ("Dockerfile" "README.md" "requirements.txt" "app.py" "server.py" "ubyt.xlsx" "Elsevier.xlsx" "Wiley.xlsx") do (
    if not exist "%SOURCE_DIR%\%%~F" (
        echo ERROR: Required file missing: %SOURCE_DIR%\%%~F
        exit /b 1
    )
)
for %%F in ("static\index.html" "static\app.js" "static\styles.css") do (
    if not exist "%SOURCE_DIR%\%%~F" (
        echo ERROR: Required file missing: %SOURCE_DIR%\%%~F
        exit /b 1
    )
)
findstr /B /C:"sdk: docker" "%SOURCE_DIR%\README.md" >nul || (
    echo ERROR: README.md is missing `sdk: docker` in the YAML frontmatter.
    exit /b 1
)
findstr /B /C:"app_port: 7860" "%SOURCE_DIR%\README.md" >nul || (
    echo ERROR: README.md is missing `app_port: 7860` in the YAML frontmatter.
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
echo [2/7] Validating Docker build...
if "%SKIP_DOCKER_CHECK%"=="1" (
    echo Docker preflight skipped by request.
) else (
    where docker >nul 2>nul || (
        echo ERROR: docker not found in PATH. Use /skip-docker-check to bypass this preflight.
        exit /b 1
    )
    docker build -t %DOCKER_TAG% "%SOURCE_DIR%" || (
        echo ERROR: docker build failed. Aborting push.
        exit /b 1
    )
    docker image rm %DOCKER_TAG% >nul 2>nul
)

echo.
echo [3/7] Preparing local HF Space clone...
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
echo [4/7] Syncing files to Space working tree...
robocopy "%SOURCE_DIR%" "%WORK_DIR%" /MIR /XD .git .venv __pycache__ .pytest_cache .mypy_cache .vscode node_modules .playwright-mcp /XF "~$*.xlsx"
set "ROBOCOPY_EXIT=%ERRORLEVEL%"
if %ROBOCOPY_EXIT% GEQ 8 (
    echo ERROR: robocopy failed with exit code %ROBOCOPY_EXIT%.
    if /I not "%WORK_DIR%"=="%SPACE_DIR%" rmdir /S /Q "%WORK_DIR%" 2>nul
    exit /b %ROBOCOPY_EXIT%
)

del /Q "%WORK_DIR%\~$*.xlsx" 2>nul

echo.
echo [5/7] Checking for changes...
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
echo [6/7] Creating commit...
git add . || (
    popd
    if /I not "%WORK_DIR%"=="%SPACE_DIR%" rmdir /S /Q "%WORK_DIR%" 2>nul
    exit /b 1
)
git diff --cached --quiet && (
    echo No staged changes detected after sync. Nothing to commit.
    popd
    if /I not "%WORK_DIR%"=="%SPACE_DIR%" rmdir /S /Q "%WORK_DIR%" 2>nul
    exit /b 0
)
git commit -m "%COMMIT_MESSAGE%" || (
    echo ERROR: git commit failed.
    popd
    if /I not "%WORK_DIR%"=="%SPACE_DIR%" rmdir /S /Q "%WORK_DIR%" 2>nul
    exit /b 1
)

echo.
echo [7/7] Pushing to Hugging Face Space...
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
echo   push_hf_space.bat [/dry-run] [/skip-docker-check] [space_repo] [space_dir] [commit_message]
echo.
echo Examples:
echo   push_hf_space.bat
echo   push_hf_space.bat /dry-run
echo   push_hf_space.bat /skip-docker-check
echo   push_hf_space.bat https://huggingface.co/spaces/kmkarakaya/dergitarama C:\Codes\dergitarama-space "Deploy latest app"
exit /b 0