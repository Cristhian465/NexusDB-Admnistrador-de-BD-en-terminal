# SafeBridge API

SafeBridge API es un servicio backend **headless** (sin interfaz gráfica) construido en **Rust** con **Axum**, diseñado para validar backups de bases de datos en entornos aislados (Sandbox) mediante contenedores Docker.

## Endpoints

### 1. Iniciar una Validación (Subir Archivo)
**Endpoint:** `POST /api/v1/validation/run`
**Rol:** Recibe tu archivo de base de datos directamente, crea el entorno aislado (sandbox), lo restaura y lo analiza. El archivo se guarda temporalmente en el servidor y se borra al finalizar.
**Formato de entrada:** `multipart/form-data`

**Campos del Formulario (Request):**
- `engine` (Texto): El motor de base de datos. Valores soportados: `mysql`, `postgres`, `sqlserver`, `mongodb`.
- `database_name` (Texto, Opcional): El nombre de la base de datos si lo requiere el motor.
- `file` (Archivo): El archivo `.sql` o `.bak` de tu backup.

**Response (202 Accepted):**
```json
{
  "task_id": "uuid-generado",
  "status": "queued",
  "message": "Validación iniciada en segundo plano. Consulte el estado con GET /api/v1/validation/{task_id}/report"
}
```

### 2. Consultar el Reporte de la Validación
**Endpoint:** `GET /api/v1/validation/{id}/report`
**Rol:** Devuelve el estado actual y el reporte detallado de una tarea de validación.

**Response en Proceso (200 OK):**
```json
{
  "task_id": "uuid-generado",
  "status": "processing",
  "progress": "Restaurando base de datos en contenedor temporal...",
  "report": null
}
```

**Response Finalizado (200 OK):**
```json
{
  "task_id": "uuid-generado",
  "status": "completed",
  "progress": "",
  "report": {
    "integrity_valid": true,
    "execution_time_seconds": 45,
    "tables_validated": 24,
    "warnings": [],
    "critical_errors": [],
    "logs": [
      "[15:30:10] Docker está disponible.",
      "[15:30:15] Contenedor levantado exitosamente...",
      "[15:30:42] Archivo temporal eliminado exitosamente."
    ]
  }
}
```

### 3. Historial de Todas las Tareas
**Endpoint:** `GET /api/v1/validation/tasks`
**Rol:** Lista todas las tareas de validación registradas, ordenadas de la más reciente a la más antigua.

**Response (200 OK):**
```json
{
  "tasks": [
    {
      "task_id": "uuid-generado",
      "status": "completed",
      "progress": null,
      "backup_path": "/tmp/uuid_backup.sql",
      "engine": "mysql",
      "database_name": "mi_db",
      "created_at": "2026-06-11 15:00:00",
      "finished_at": "2026-06-11 15:01:45"
    }
  ]
}
```

### 4. Revisar la Salud del Servidor
**Endpoint:** `GET /health`
**Rol:** Verifica el estado del servidor y la disponibilidad de Docker. Ideal para verificar la conexión antes de enviar un archivo.

**Response (200 OK):**
```json
{
  "status": "ok",
  "service": "SafeBridge API",
  "version": "1.0.0",
  "docker_available": true,
  "timestamp": "2026-06-11 15:25:00"
}
```

## Motores Soportados

| Motor      | Imagen Docker                              |
|------------|---------------------------------------------|
| PostgreSQL | `postgres:14-alpine`                       |
| MySQL      | `mysql:8.0`                                |
| SQL Server | `mcr.microsoft.com/mssql/server:2022-latest` |
| MongoDB    | `mongo:7`                                  |

## Prerrequisitos

- **Rust** (con `cargo`)
- **Docker** instalado y en ejecución

## Ejecución (Docker)

```bash
# 1. Construir la imagen
docker build -t safebridge-api .

# 2. Ejecutar el contenedor (montando el socket de Docker)
docker run -d --name safebridge_api -p 3000:3000 -v /var/run/docker.sock:/var/run/docker.sock safebridge-api

# El servidor inicia en http://localhost:3000
```

> Para más detalles sobre la instalación en un servidor VPS, consulta el archivo [INSTALACION.md](INSTALACION.md).

## Estructura del Proyecto

```text
safebridge-api/
├── src/
│   ├── main.rs          # Servidor Axum y enrutamiento
│   ├── api.rs           # Handlers de los endpoints (POST/GET)
│   ├── sandbox.rs       # Lógica de validación en Docker Sandbox
│   ├── docker.rs        # Utilidades para ejecutar comandos Docker
│   ├── db.rs            # Inicialización de SQLite
│   ├── models.rs        # Estructuras de datos y DTOs
│   ├── crypto.rs        # Cifrado AES-256-GCM
│   ├── connections.rs   # CRUD de conexiones (disponible)
│   └── logs.rs          # Consultas de historial (disponible)
├── Cargo.toml
└── PLAN_API.md
```

## Tecnologías

- **Axum** — Framework web de alto rendimiento
- **Tokio** — Runtime asíncrono
- **rusqlite** — Base de datos SQLite embebida
- **tower-http** — CORS middleware
- **Docker** — Sandbox de validación
