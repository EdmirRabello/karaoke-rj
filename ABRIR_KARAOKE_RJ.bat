@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM ================================
REM  Karaokê RJ - Catálogo (Auto)
REM  1) Cria venv
REM  2) Instala dependências
REM  3) Importa banco.xlsx (se existir)
REM  4) Roda o site em http://127.0.0.1:8000
REM ================================

echo.
echo ================================
echo   Catálogo Karaokê RJ - START
echo ================================
echo.

REM Garante que estamos na pasta do projeto (onde está este .bat)
cd /d "%~dp0"

REM 0) Verifica Python
where python >nul 2>nul
if errorlevel 1 (
  echo [ERRO] Python não encontrado no PATH.
  echo Instale Python 3.10+ e marque "Add Python to PATH".
  echo Link: https://www.python.org/downloads/
  echo.
  pause
  exit /b 1
)

REM 1) Cria ambiente virtual se não existir
if not exist ".venv\Scripts\python.exe" (
  echo [1/4] Criando ambiente virtual (.venv)...
  python -m venv .venv
  if errorlevel 1 (
    echo [ERRO] Falha ao criar venv.
    pause
    exit /b 1
  )
) else (
  echo [1/4] Ambiente virtual (.venv) já existe.
)

REM 2) Instala dependências
echo [2/4] Instalando dependências...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERRO] Falha ao instalar dependências.
  echo Dica: feche o PyCharm/Terminal e tente novamente.
  pause
  exit /b 1
)

REM 3) Importa Excel se existir
if exist "banco.xlsx" (
  echo [3/4] Importando banco.xlsx para o banco local...
  ".venv\Scripts\python.exe" import_excel.py "banco.xlsx"
  if errorlevel 1 (
    echo [ERRO] Falha ao importar o banco.xlsx.
    pause
    exit /b 1
  )
) else (
  echo [3/4] banco.xlsx NÃO encontrado nesta pasta.
  echo Coloque o arquivo banco.xlsx aqui e rode novamente para importar.
)

REM 4) Inicia servidor
echo [4/4] Iniciando servidor...
echo.
echo Abra no navegador:
echo   http://127.0.0.1:8000
echo.
echo Para PARAR o servidor: pressione CTRL + C aqui.
echo.

REM Abre o navegador automaticamente
start "" "http://127.0.0.1:8000" >nul 2>nul

".venv\Scripts\python.exe" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

echo.
echo Servidor encerrado.
pause
endlocal
