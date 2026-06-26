# Reporte de Error - SafeBridge API

Este documento contiene el análisis técnico del fallo en la validación de backups de MySQL en el VPS y los pasos recomendados para solucionarlo.

---

## 1. Conflicto de Volúmenes (Docker-in-Docker)

**Error observado en el log del Sandbox:**
```text
[20:21:45] Advertencia en restauración: sh: line 1: /backup/cfcdaaea-555d-4ce4-898c-59de7707fbb2_olimpiadas_upt.sql: No such file or directory
```

### Causa
La API de SafeBridge corre dentro de un contenedor Docker y guarda el archivo subido en su `/tmp` interno. Al instanciar el contenedor temporal de MySQL (como contenedor hermano) mediante el socket de Docker, el daemon de Docker busca el archivo en el `/tmp` del host real y no en el de la API. Por lo tanto, el directorio `/backup` en el sandbox queda vacío y no se restaura nada.

### Solución recomendada
En el backend Rust de la API, después de crear el contenedor de base de datos y antes de ejecutar la restauración, copia el archivo de backup directamente al contenedor temporal:

```bash
docker cp /tmp/[task_id]_[archivo].sql [container_id]:/backup.sql
```

Luego, ejecuta la restauración apuntando al archivo local `/backup.sql` dentro del contenedor.

---

## 2. Espera Insuficiente para la Inicialización de MySQL

**Error observado en el log del Sandbox:**
```text
[20:21:45] Error al consultar tablas: mysql: [Warning] Using a password on the command line interface can be insecure.
ERROR 2002 (HY000): Can't connect to local MySQL server through socket '/var/run/mysqld/mysqld.sock' (2)
```

### Causa
La API tiene una espera estática de 10 segundos para que MySQL esté disponible. En un VPS, el primer arranque del contenedor de MySQL (creación de directorios, llaves SSL y el usuario root) suele tardar más de 15 segundos. Al realizar la validación antes de que el servidor cree el socket de conexión, el comando falla.

### Solución recomendada
Sustituir el tiempo de espera fijo (sleep) por un bucle de comprobación de estado de conexión real. Ejecuta el siguiente comando en bucle antes de iniciar la restauración:

```bash
docker exec [container_id] mysqladmin ping -u root -p[contraseña]
```

Continúa con la importación y el conteo de tablas solo cuando este comando responda exitosamente (retorno `0`).
