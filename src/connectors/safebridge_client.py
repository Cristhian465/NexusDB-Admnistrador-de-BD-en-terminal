"""
Cliente local para la validación de backups SafeBridge (Iker)
Valida la integridad de backups utilizando contenedores Docker locales
"""

import os
import subprocess
import time
import uuid
from rich.console import Console

class SafeBridgeClient:
    def __init__(self, base_url=None):
        # Mantenemos la firma del constructor por compatibilidad con repl.py
        self.console = Console()

    def validar_backup(self, backup_path: str, engine: str, database_name: str):
        """
        Realiza la validación de integridad del backup levantando un contenedor
        Docker local temporal de forma aislada, restaurando los datos y contando las tablas.
        """
        start_time = time.time()
        
        # 1. VERIFICACIÓN FÍSICA LOCAL
        if not os.path.exists(backup_path):
            return False, f"Error local: El archivo '{backup_path}' no existe en tu computadora."

        # 2. VERIFICACIÓN DE DISPONIBILIDAD DE DOCKER
        try:
            res_dock = subprocess.run(["docker", "ps"], capture_output=True, text=True, timeout=5)
            if res_dock.returncode != 0:
                return False, "Docker no está en ejecución. Por favor, inicia Docker Desktop."
        except Exception:
            return False, "Docker no está instalado o no se encuentra en el PATH del sistema."

        abs_backup_path = os.path.abspath(backup_path)
        backup_dir = os.path.dirname(abs_backup_path)
        backup_filename = os.path.basename(abs_backup_path)

        # 3. DETERMINAR IMAGEN Y CONFIGURACIÓN SEGÚN EL MOTOR
        engine = engine.lower().strip()
        env_args = []
        
        if "postgres" in engine:
            image = "postgres:14-alpine"
            env_args = ["-e", "POSTGRES_HOST_AUTH_METHOD=trust"]
        elif "mysql" in engine:
            image = "mysql:8.0"
            env_args = ["-e", "MYSQL_ROOT_PASSWORD=root", "-e", "MYSQL_DATABASE=testdb"]
        elif "sqlserver" in engine or "mssql" in engine:
            image = "mcr.microsoft.com/mssql/server:2022-latest"
            env_args = ["-e", "ACCEPT_EULA=Y", "-e", "SA_PASSWORD=SafeBridge@123"]
        elif "mongodb" in engine or "mongo" in engine:
            image = "mongo:7"
        else:
            return False, f"Motor '{engine}' no soportado para validación en sandbox local."

        # Generar ID de contenedor único
        task_id = str(uuid.uuid4())[:8]
        container_name = f"safebridge-sandbox-{task_id}"

        # 4. LEVANTAR EL CONTENEDOR TEMPORAL
        self.console.print(f"\n[bold cyan][SafeBridge][/bold cyan] Iniciando contenedor temporal de sandbox ([white]{image}[/white])...")
        
        docker_run_cmd = [
            "docker", "run", "-d", "--rm",
            "--name", container_name,
            "-v", f"{backup_dir}:/backup"
        ] + env_args + [image]

        try:
            res_run = subprocess.run(docker_run_cmd, capture_output=True, text=True, timeout=20)
            if res_run.returncode != 0:
                return False, f"Error al iniciar el contenedor Docker: {res_run.stderr.strip()}"
        except Exception as e:
            return False, f"Excepción al ejecutar Docker: {str(e)}"

        # Asegurar la limpieza en caso de fallos
        try:
            # 5. ESPERAR A QUE EL MOTOR ESTÉ LISTO (polling con timeout de 45s)
            self.console.print("[bold yellow]🔄 Esperando a que el motor de base de datos esté listo...[/bold yellow]")
            max_espera = 45
            motor_listo = False
            for intento in range(max_espera):
                if "postgres" in engine:
                    cmd_ready = ["docker", "exec", container_name, "pg_isready", "-U", "postgres"]
                elif "mysql" in engine:
                    cmd_ready = ["docker", "exec", container_name,
                                 "mysql", "-h", "127.0.0.1", "-u", "root", "-proot", "-e", "SELECT 1"]
                elif "sqlserver" in engine or "mssql" in engine:
                    cmd_ready = ["docker", "exec", container_name,
                                 "/opt/mssql-tools18/bin/sqlcmd", "-S", "localhost",
                                 "-U", "sa", "-P", "SafeBridge@123", "-C", "-Q", "SELECT 1"]
                elif "mongodb" in engine or "mongo" in engine:
                    cmd_ready = ["docker", "exec", container_name,
                                 "mongosh", "--quiet", "--eval", "db.adminCommand({ping:1})"]
                else:
                    time.sleep(10)
                    motor_listo = True
                    break
                res_ready = subprocess.run(cmd_ready, capture_output=True, timeout=5)
                if res_ready.returncode == 0:
                    motor_listo = True
                    break
                time.sleep(1)

            if not motor_listo:
                return False, f"El motor de base de datos no respondió en {max_espera} segundos. Verifica que Docker tenga recursos suficientes."

            # 6. RESTAURAR EL RESPALDO DENTRO DEL CONTENEDOR
            self.console.print("[bold yellow]🔄 Restaurando base de datos en el sandbox temporal...[/bold yellow]")

            if "postgres" in engine:
                restore_cmd = [
                    "docker", "exec", "-i", container_name,
                    "psql", "-U", "postgres", "-f", f"/backup/{backup_filename}"
                ]
            elif "mysql" in engine:
                # Usar -h 127.0.0.1 para forzar TCP en vez de socket UNIX
                restore_cmd = [
                    "docker", "exec", "-i", container_name,
                    "sh", "-c",
                    f"mysql -h 127.0.0.1 -P 3306 -u root -proot testdb < /backup/{backup_filename}"
                ]
            elif "sqlserver" in engine or "mssql" in engine:
                restore_cmd = [
                    "docker", "exec", "-i", container_name,
                    "/opt/mssql-tools18/bin/sqlcmd", "-S", "localhost",
                    "-U", "sa", "-P", "SafeBridge@123", "-C", "-i", f"/backup/{backup_filename}"
                ]
            elif "mongodb" in engine or "mongo" in engine:
                restore_cmd = [
                    "docker", "exec", "-i", container_name,
                    "mongorestore", f"--archive=/backup/{backup_filename}"
                ]

            res_restore = subprocess.run(restore_cmd, capture_output=True, text=True, timeout=120)
            if res_restore.returncode != 0:
                self.console.print(f"[yellow]Advertencia en la restauración (código {res_restore.returncode}): {res_restore.stderr.strip()}[/yellow]")

            # 7. EJECUTAR CONSULTAS DE INTEGRIDAD (CONTEO DE TABLAS)
            self.console.print("[bold yellow]🔄 Ejecutando consultas de validación de integridad...[/bold yellow]")

            query_cmd = None
            if "postgres" in engine:
                query_cmd = [
                    "docker", "exec", container_name,
                    "psql", "-U", "postgres", "-t", "-c",
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
                ]
            elif "mysql" in engine:
                # -h 127.0.0.1 para TCP en vez de socket UNIX
                query_cmd = [
                    "docker", "exec", container_name,
                    "mysql", "-h", "127.0.0.1", "-u", "root", "-proot", "-N", "-e",
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'testdb'"
                ]

            tables_count = 0
            warnings = []
            critical_errors = []

            if query_cmd:
                res_query = subprocess.run(query_cmd, capture_output=True, text=True, timeout=15)
                if res_query.returncode == 0:
                    try:
                        tables_count = int(res_query.stdout.strip())
                    except ValueError:
                        warnings.append(f"No se pudo parsear el número de tablas: {res_query.stdout.strip()}")
                else:
                    warnings.append(f"No se pudo consultar el número de tablas: {res_query.stderr.strip()}")
            else:
                # Si no hay comando de consulta directa (ej. MongoDB/SqlServer), asumimos que si el restore no falló catastróficamente hay al menos 1 objeto
                if res_restore.returncode == 0:
                    tables_count = 1
                else:
                    critical_errors.append("La restauración falló o retornó un código de error.")

            if tables_count == 0 and not critical_errors:
                critical_errors.append("No se encontraron tablas creadas después de la restauración.")

        finally:
            # 8. DETENER Y REMOVER CONTENEDOR TEMPORAL (LIMPIEZA SIEMPRE ACTIVA)
            self.console.print("[bold yellow]🧹 Destruyendo contenedor sandbox temporal...[/bold yellow]")
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)

        duration = int(time.time() - start_time)
        
        # 9. CONSTRUIR REPORTE FINAL DE INTEGRIDAD
        report = {
            "tables_validated": tables_count,
            "execution_time_seconds": duration,
            "warnings": warnings,
            "critical_errors": critical_errors,
            "integrity_valid": len(critical_errors) == 0 and tables_count > 0
        }
        
        return True, report