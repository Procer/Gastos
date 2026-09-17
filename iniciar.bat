@echo off
cd /d "%~dp0"

echo Revisando que Docker este corriendo...
docker info >nul 2>&1
if errorlevel 1 (
    echo Docker no esta corriendo, lo estoy iniciando...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    :esperar_docker
    ping -n 4 127.0.0.1 >nul
    docker info >nul 2>&1
    if errorlevel 1 goto esperar_docker
)

echo Levantando el agente de gastos...
docker compose up -d

echo Esperando a que el agente termine de iniciar...
ping -n 7 127.0.0.1 >nul

echo Aplicando migraciones pendientes...
docker compose exec -T app python -m app.migrate

echo Listo! Abriendo el sistema en tu navegador...
start http://localhost:8000/docs
start http://localhost:8081
