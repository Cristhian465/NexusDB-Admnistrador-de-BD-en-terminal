"""
Módulo REPL - Read-Eval-Print Loop
Bucle principal que lee comandos y los ejecuta
"""

import sys
import os
import csv
import shlex

# Agregar la carpeta actual al path para poder importar
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from connectors.sqlite_connector import SQLiteConnector
from connectors.postgres_connector import PostgresConnector
from connectors.mysql_connector import MySQLConnector
from connectors.mongodb_connector import MongoDBConnector
from connectors.redis_connector import RedisConnector
from connectors.cassandra_connector import CassandraConnector
from formatters.table_formatter import TableFormatter
# Importación del nuevo conector para el proyecto de Iker
from connectors.safebridge_client import SafeBridgeClient

# Importación del motor ETL de Jimmy (Migrador)
from utilidades.detector import DetectorBaseDatos
from extraccion.conector import ConectorOrigen
from transformacion.mapeador import MapeadorDatos
from carga.cargador import CargadorDestino

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import print as rprint


class REPL:
    """Bucle principal de la aplicación"""

    def __init__(self, mode='rel'):
        self.running = True
        self.mode = mode
        self.console = Console()
        self.connector = None
        self.formatter = TableFormatter()
        self.last_results = None  # Almacena el resultado del último SELECT

    def _get_prompt(self):
        """Genera el prompt dinámicamente según el estado de la conexión"""
        base = "dbcli-rel" if self.mode == "rel" else "dbcli-nosql"
        if self.connector and self.connector.is_connected:
            db_type = self.connector.get_type().lower()
            db_info = self.connector.get_info()
            # Extraer solo el nombre del archivo si es path completo
            db_name = os.path.basename(db_info)
            return f"[{base} | {db_type}: {db_name}] > "
        return f"{base} > "

    def run(self):
        """Ejecuta el bucle principal"""
        while self.running:
            try:
                current_prompt = self._get_prompt()
                command = input(current_prompt).strip()
                if not command:
                    continue
                
                # Try-except global para capturar errores de ejecución sin cerrar la app
                try:
                    self.execute(command)
                except Exception as e:
                    rprint(f"\n[bold red]ERROR de ejecución:[/bold red] [white]{e}[/white]")
                    rprint("[yellow]La aplicación sigue activa. Intenta de nuevo.[/yellow]\n")
                    
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                rprint("\n[yellow]Usa 'exit' para salir correctamente.[/yellow]")
                continue

    def execute(self, command: str):
        """Ejecuta un comando según su tipo"""
        cmd = command.lower().strip()

        if cmd == "exit":
            self._exit()
        elif cmd == "help":
            self._help()
        elif cmd.startswith("validate backup"): # Captura el comando de validación externa
            self._handle_safebridge_validation(command)
        elif cmd.startswith("migrate"): # Captura el comando de migración ETL de Jimmy
            self._migrate(command)
        elif cmd.startswith("connect"):
            self._connect(command)
        elif cmd == "status":
            self._status()
        elif cmd == "disconnect":
            self._disconnect()
        elif cmd.startswith("export_db"):
            self._export_db(command)
        elif cmd.startswith("import_db"):
            self._import_script(command)
        elif cmd.startswith("export_sql"):
            self._export_sql(command)
        elif cmd.startswith("export"):
            self._export(command)
        elif cmd.startswith("import"):
            self._import_script(command)
        else:
            if not self.connector or not self.connector.is_connected:
                rprint("[bold red]ERROR:[/bold red] No hay conexión activa. [yellow]Usa 'connect' primero.[/yellow]")
                return

            if self.mode == "rel":
                if cmd.startswith("select"):
                    self._select(command)
                elif cmd.startswith("insert"):
                    self._insert(command)
                elif cmd.startswith("update"):
                    self._update(command)
                elif cmd.startswith("delete"):
                    self._delete(command)
                elif cmd.startswith("create table"):
                    self._create_table(command)
                elif cmd.startswith("drop table"):
                    self._drop_table(command)
                elif cmd == "show tables":
                    self._show_tables()
                else:
                    rprint(f"[bold red]ERROR: Comando no reconocido:[/bold red] [white]{command}[/white]")
                    rprint("   Usa [bold cyan]'help'[/bold cyan] para ver los comandos disponibles")
            else:
                if cmd in ["show collections", "show keys", "show tables"]:
                    self._show_tables()
                else:
                    self._execute_nosql_query(command)

    # ==================== COMANDOS BÁSICOS ====================

    def _exit(self):
        """Salir de la aplicación"""
        if self.connector and self.connector.is_connected:
            self._disconnect()
        rprint("\n[bold green]Hasta luego[/bold green]")
        self.running = False

    def _help(self):
        """Mostrar ayuda"""
        help_text = Text()
        if self.mode == "rel":
            help_text.append("\nCONEXIÓN RELACIONAL:\n", style="bold cyan")
            help_text.append("  connect sqlite <ruta>                       - Ej: connect sqlite test.db\n")
            help_text.append("  connect postgres <db> <user> <pass> [host]  - Ej: connect postgres mi_db postgres 123\n")
            help_text.append("  connect mysql <db> <user> <pass> [host]     - Ej: connect mysql mi_db root 123\n")
            
            help_text.append("\nCONSULTAS (CRUD):\n", style="bold green")
            help_text.append("  select * from <tabla> [where ...]           - Ej: select * from usuarios\n")
            help_text.append("  insert into <tabla> (...) values (...)      - Ej: insert into usuarios (nombre) values ('Ana')\n")
            help_text.append("  update <tabla> set col=val where ...        - Ej: update usuarios set edad=30 where id=1\n")
            help_text.append("  delete from <tabla> where ...               - Ej: delete from usuarios where id=1\n")
            
            help_text.append("\nESTRUCTURA:\n", style="bold magenta")
            help_text.append("  create table <nombre> (...)                 - Crear nueva tabla\n")
            help_text.append("  drop table <nombre>                         - Eliminar tabla\n")
            help_text.append("  show tables                                 - Listar tablas existentes\n")
        else:
            help_text.append("\nCONEXIÓN NOSQL:\n", style="bold cyan")
            help_text.append("  connect mongodb <db> [host] [puerto]        - Ej: connect mongodb testdb localhost 27017\n")
            help_text.append("  connect redis [db_index] [host] [puerto]    - Ej: connect redis 0 localhost 6379\n")
            help_text.append("  connect cassandra <keyspace> [host]         - Ej: connect cassandra testks localhost\n")
            
            help_text.append("\nCOMANDOS NOSQL:\n", style="bold green")
            help_text.append("  MongoDB:\n")
            help_text.append("    find <coleccion> <json_filtro>            - Ej: find usuarios {\"edad\": 30}\n")
            help_text.append("    insert <coleccion> <json_doc>             - Ej: insert usuarios {\"nombre\": \"Ana\", \"edad\": 30}\n")
            help_text.append("    update <coleccion> <filtro> <set>         - Ej: update usuarios {\"nombre\": \"Ana\"} {\"edad\": 31}\n")
            help_text.append("    delete <coleccion> <json_filtro>          - Ej: delete usuarios {\"nombre\": \"Ana\"}\n")
            help_text.append("  Redis:\n")
            help_text.append("    set <clave> <valor>                       - Ej: set saludo hola\n")
            help_text.append("    get <clave>                               - Ej: get saludo\n")
            help_text.append("    del <clave>                               - Ej: del saludo\n")
            help_text.append("    keys <patron>                             - Ej: keys *\n")
            help_text.append("  Cassandra:\n")
            help_text.append("    Soporte para comandos CQL como select, insert, update...\n")
            
            help_text.append("\nESTRUCTURA:\n", style="bold magenta")
            help_text.append("  show collections / show keys / show tables  - Listar estructuras existentes\n")

        help_text.append("\nCOMUNES:\n", style="bold yellow")
        help_text.append("  status                                      - Ver estado de conexión\n")
        help_text.append("  disconnect                                  - Cerrar sesión activa\n")
        help_text.append("  import <archivo.sql>                        - Importar y ejecutar script SQL/NoSQL\n")
        help_text.append("  import_db <archivo.sql>                     - Importar un backup de BD completa\n")
        help_text.append("  export <archivo.csv>                        - Exportar últimos resultados a CSV\n")
        help_text.append("  export_sql <tabla> <archivo.sql>            - Exportar tabla/colección a script\n")
        help_text.append("  export_db <archivo.sql>                     - Exportar BD completa (esquema y datos)\n")
        help_text.append("  migrate <origen> <destino> <salida> [--sim] - Migrar base de datos por ETL (Jimmy)\n")
        help_text.append("  validate backup <ruta> <motor> <db_name>    - Validar integridad de backup en Docker (Iker)\n")
        help_text.append("  help                                        - Muestra esta ayuda\n")
        help_text.append("  exit                                        - Salir de la aplicación\n")

        self.console.print(Panel(help_text, title="[bold white]COMANDOS DISPONIBLES[/bold white]", border_style="blue"))

    def _connect(self, command: str):
        """Conectar a una base de datos"""
        parts = command.split()
        if len(parts) < 2:
            print("❌ Uso: connect <tipo> <parámetros>")
            print("   Tipos: sqlite, postgres, mysql")
            return

        db_type = parts[1].lower()

        if db_type == "sqlite":
            if len(parts) < 3:
                print("❌ Uso: connect sqlite <ruta>")
                return
            db_path = parts[2]
            rprint(f"[bold blue]Conectando a SQLite:[/bold blue] [white]{db_path}...[/white]")
            try:
                self.connector = SQLiteConnector()
                self.connector.connect(db_path=db_path)
                rprint(f"[bold green]OK: Conectado a SQLite correctamente.[/bold green]")
            except Exception as e:
                rprint(f"[bold red]ERROR de conexión:[/bold red] {e}")
                self.connector = None

        elif db_type == "postgres":
            if len(parts) < 5:
                print("❌ Uso: connect postgres <db> <usuario> <contraseña> [host] [puerto]")
                return
            db_name = parts[2]
            user = parts[3]
            password = parts[4]
            host = parts[5] if len(parts) > 5 else "localhost"
            port = parts[6] if len(parts) > 6 else "5432"
            print(f"🔌 Conectando a PostgreSQL: {db_name}...")
            try:
                self.connector = PostgresConnector()
                self.connector.connect(
                    dbname=db_name,
                    user=user,
                    password=password,
                    host=host,
                    port=port
                )
                print(f"✅ Conectado a PostgreSQL: {db_name}")
            except Exception as e:
                print(f"❌ Error: {e}")
                self.connector = None

        elif db_type == "mysql":
            if len(parts) < 5:
                print("❌ Uso: connect mysql <db> <usuario> <contraseña> [host] [puerto]")
                return
            db_name = parts[2]
            user = parts[3]
            password = parts[4]
            host = parts[5] if len(parts) > 5 else "localhost"
            port = parts[6] if len(parts) > 6 else "3306"
            print(f"🔌 Conectando a MySQL: {db_name}...")
            try:
                self.connector = MySQLConnector()
                self.connector.connect(
                    database=db_name,
                    user=user,
                    password=password,
                    host=host,
                    port=port
                )
                print(f"✅ Conectado a MySQL: {db_name}")
            except Exception as e:
                print(f"❌ Error: {e}")
                self.connector = None

        elif db_type == "mongodb":
            if self.mode != "nosql":
                print("❌ MongoDB solo está disponible en modo NoSQL")
                return
            if len(parts) < 3:
                print("❌ Uso: connect mongodb <db> [host] [puerto]")
                return
            db_name = parts[2]
            host = parts[3] if len(parts) > 3 else "localhost"
            port = parts[4] if len(parts) > 4 else "27017"
            print(f"🔌 Conectando a MongoDB: {db_name}...")
            try:
                self.connector = MongoDBConnector()
                self.connector.connect(db_name=db_name, host=host, port=port)
                print(f"✅ Conectado a MongoDB: {db_name}")
            except Exception as e:
                print(f"❌ Error: {e}")
                self.connector = None

        elif db_type == "redis":
            if self.mode != "nosql":
                print("❌ Redis solo está disponible en modo NoSQL")
                return
            db_index = parts[2] if len(parts) > 2 else "0"
            host = parts[3] if len(parts) > 3 else "localhost"
            port = parts[4] if len(parts) > 4 else "6379"
            print(f"🔌 Conectando a Redis DB {db_index}...")
            try:
                self.connector = RedisConnector()
                self.connector.connect(db_index=db_index, host=host, port=port)
                print(f"✅ Conectado a Redis DB {db_index}")
            except Exception as e:
                print(f"❌ Error: {e}")
                self.connector = None

        elif db_type == "cassandra":
            if self.mode != "nosql":
                print("❌ Cassandra solo está disponible en modo NoSQL")
                return
            if len(parts) < 3:
                print("❌ Uso: connect cassandra <keyspace> [host]")
                return
            keyspace = parts[2]
            host = parts[3] if len(parts) > 3 else "localhost"
            print(f"🔌 Conectando a Cassandra keyspace: {keyspace}...")
            try:
                self.connector = CassandraConnector()
                self.connector.connect(keyspace=keyspace, host=host)
                print(f"✅ Conectado a Cassandra keyspace: {keyspace}")
            except Exception as e:
                print(f"❌ Error: {e}")
                self.connector = None

        else:
            print(f"❌ Tipo de base de datos no soportado: {db_type}")
            if self.mode == "rel":
                print("   Tipos soportados: sqlite, postgres, mysql")
            else:
                print("   Tipos soportados: mongodb, redis, cassandra")

    def _status(self):
        """Mostrar estado de la conexión"""
        status_text = Text()
        if self.connector and self.connector.is_connected:
            status_text.append("OK: ESTADO: CONECTADO\n", style="bold green")
            status_text.append(f"TIPO: {self.connector.get_type()}\n", style="white")
            status_text.append(f"INFO: {self.connector.get_info()}", style="cyan")
        else:
            status_text.append("ERROR: ESTADO: NO CONECTADO", style="bold red")

        self.console.print(Panel(status_text, title="[bold white]INFORMACIÓN DE CONEXIÓN[/bold white]", expand=False))

    def _disconnect(self):
        """Desconectar de la base de datos"""
        if self.connector and self.connector.is_connected:
            rprint("[bold blue]Desconectando...[/bold blue]")
            try:
                self.connector.disconnect()
                self.connector = None
                rprint("[bold green]OK: Desconectado con éxito.[/bold green]")
            except Exception as e:
                rprint(f"[bold red]ERROR al desconectar:[/bold red] {e}")
        else:
            rprint("[bold yellow]INFO: No hay conexión activa para cerrar.[/bold yellow]")

    # ==================== OPERACIONES ====================

    def _select(self, command: str):
        """Ejecutar SELECT"""
        success, data, error = self.connector.execute_query(command)
        if success:
            if data and 'columns' in data and data['columns']:
                self.last_results = data  # Guardar para exportación
                self.formatter.print_table(data['columns'], data['rows'])
                rprint(f"\n[bold cyan]INFO: Total:[/bold cyan] [white]{len(data['rows'])} fila(s)[/white]")
            elif data and 'affected_rows' in data:
                rprint(f"[bold green]OK: Éxito:[/bold green] [white]{data['affected_rows']} fila(s) afectada(s)[/white]")
            else:
                rprint("[bold yellow]INFO: Consulta ejecutada sin resultados.[/bold yellow]")
        else:
            rprint(f"[bold red]ERROR SQL:[/bold red] [white]{error}[/white]")

    def _export(self, command: str):
        """Exporta los últimos resultados a un archivo CSV"""
        parts = command.split()
        if len(parts) < 2:
            rprint("[bold red]ERROR:[/bold red] Debes especificar un nombre de archivo. [yellow]Ej: export resultados.csv[/yellow]")
            return

        if not self.last_results:
            rprint("[bold yellow]INFO: No hay resultados para exportar.[/bold yellow] [white]Primero realiza un SELECT.[/white]")
            return

        filename = parts[1]
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(self.last_results['columns'])
                writer.writerows(self.last_results['rows'])
            rprint(f"[bold green]OK: Datos exportados correctamente a:[/bold green] [white]{filename}[/white]")
        except Exception as e:
            rprint(f"[bold red]ERROR al exportar:[/bold red] {e}")

    def _import_script(self, command: str):
        """Importa y ejecuta un archivo .sql o de script"""
        if not self.connector or not self.connector.is_connected:
            rprint("[bold red]ERROR:[/bold red] No hay conexión activa. [yellow]Conéctate a una BD antes de importar.[/yellow]")
            return

        parts = command.split()
        if len(parts) < 2:
            rprint("[bold red]ERROR:[/bold red] Debes especificar un archivo. [yellow]Ej: import script.sql[/yellow]")
            return

        filename = parts[1]
        if not os.path.exists(filename):
            rprint(f"[bold red]ERROR:[/bold red] El archivo '{filename}' no existe.")
            return

        rprint(f"[bold blue]Importando script desde:[/bold blue] [white]{filename}[/white]")
        
        try:
            if self.mode == "rel":
                db_type = self.connector.get_type().lower()
                if "postgres" in db_type:
                    import subprocess
                    env = os.environ.copy()
                    if hasattr(self.connector, 'password') and self.connector.password:
                        env['PGPASSWORD'] = self.connector.password
                    
                    cmd = [
                        "psql",
                        "-h", self.connector.host,
                        "-p", str(self.connector.port),
                        "-U", self.connector.user,
                        "-d", self.connector.dbname,
                        "-f", filename
                    ]
                    rprint("[bold yellow]INFO:[/bold yellow] Ejecutando psql de sistema...")
                    try:
                        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
                        if result.returncode == 0:
                            rprint("[bold green]OK: Importación finalizada con psql.[/bold green]")
                        else:
                            rprint(f"[bold red]ERROR psql:[/bold red]\n{result.stderr}")
                    except FileNotFoundError:
                        rprint("[bold red]ERROR:[/bold red] Herramienta 'psql' no encontrada en el sistema.")
                    return
                
                elif "mysql" in db_type:
                    import subprocess
                    cmd = [
                        "mysql",
                        "-h", self.connector.host,
                        f"-P{self.connector.port}",
                        f"-u{self.connector.user}",
                        self.connector.database
                    ]
                    if hasattr(self.connector, 'password') and self.connector.password:
                        cmd.append(f"-p{self.connector.password}")
                        
                    rprint("[bold yellow]INFO:[/bold yellow] Ejecutando mysql de sistema...")
                    try:
                        with open(filename, 'r', encoding='utf-8') as f:
                            result = subprocess.run(cmd, stdin=f, capture_output=True, text=True)
                        if result.returncode == 0:
                            rprint("[bold green]OK: Importación finalizada con mysql.[/bold green]")
                        else:
                            rprint(f"[bold red]ERROR mysql:[/bold red]\n{result.stderr}")
                    except FileNotFoundError:
                        rprint("[bold red]ERROR:[/bold red] Herramienta 'mysql' no encontrada en el sistema.")
                    return

                # Fallback SQLite y otros
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Dividir por punto y coma y ejecutar cada instrucción
                statements = [s.strip() for s in content.split(';') if s.strip()]
                success_count = 0
                for stmt in statements:
                    success, _, error = self.connector.execute_query(stmt)
                    if success:
                        success_count += 1
                    else:
                        rprint(f"[bold red]ERROR en instrucción:[/bold red] {stmt[:50]}...\n[red]Detalle:[/red] {error}")
                rprint(f"[bold green]OK: Importación finalizada. {success_count}/{len(statements)} instrucciones ejecutadas exitosamente.[/bold green]")
            else:
                # NoSQL: asumiendo una instrucción por línea
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()
                lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith('--') and not line.strip().startswith('//')]
                success_count = 0
                for line in lines:
                    success, _, error = self.connector.execute_query(line)
                    if success:
                        success_count += 1
                    else:
                        rprint(f"[bold red]ERROR en comando:[/bold red] {line}\n[red]Detalle:[/red] {error}")
                rprint(f"[bold green]OK: Importación finalizada. {success_count}/{len(lines)} comandos ejecutados exitosamente.[/bold green]")
        except Exception as e:
            rprint(f"[bold red]ERROR al importar script:[/bold red] {e}")

    def _export_sql(self, command: str):
        """Exporta los datos de una tabla/colección a un archivo .sql (o script)"""
        if not self.connector or not self.connector.is_connected:
            rprint("[bold red]ERROR:[/bold red] No hay conexión activa. [yellow]Conéctate a una BD antes de exportar.[/yellow]")
            return

        parts = command.split()
        if len(parts) < 3:
            rprint("[bold red]ERROR:[/bold red] Uso: export_sql <tabla_o_coleccion> <archivo.sql>")
            return

        table_name = parts[1]
        filename = parts[2]

        rprint(f"[bold blue]Exportando datos de '{table_name}' a '{filename}'...[/bold blue]")

        try:
            if self.mode == "rel":
                success, data, error = self.connector.execute_query(f"SELECT * FROM {table_name}")
                if not success:
                    rprint(f"[bold red]ERROR al consultar tabla:[/bold red] {error}")
                    return
                
                if not data or not data.get('rows'):
                    rprint(f"[bold yellow]INFO:[/bold yellow] La tabla '{table_name}' está vacía o no existe.")
                    return

                columns = data['columns']
                rows = data['rows']
                
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"-- Dump de la tabla {table_name}\n")
                    for row in rows:
                        formatted_values = []
                        for val in row:
                            if val is None:
                                formatted_values.append("NULL")
                            elif isinstance(val, (int, float)):
                                formatted_values.append(str(val))
                            else:
                                safe_val = str(val).replace("'", "''")
                                formatted_values.append(f"'{safe_val}'")
                        
                        cols_str = ", ".join(columns)
                        vals_str = ", ".join(formatted_values)
                        f.write(f"INSERT INTO {table_name} ({cols_str}) VALUES ({vals_str});\n")
                rprint(f"[bold green]OK: {len(rows)} registros exportados a '{filename}'.[/bold green]")
                
            else:
                db_type = self.connector.get_type().lower()
                
                if "mongodb" in db_type:
                    success, data, error = self.connector.execute_query(f"find {table_name} {{}}")
                    if not success:
                        rprint(f"[bold red]ERROR al consultar colección:[/bold red] {error}")
                        return
                    
                    if not data or not data.get('rows'):
                        rprint(f"[bold yellow]INFO:[/bold yellow] La colección '{table_name}' está vacía.")
                        return
                    
                    import json
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(f"// Dump de la colección {table_name}\n")
                        rows = data.get('rows', [])
                        columns = data.get('columns', [])
                        
                        for row in rows:
                            # Reconstruir el doc a partir de las columnas y la fila
                            doc = {columns[i]: row[i] for i in range(len(columns)) if row[i] != ""}
                            
                            try:
                                doc_str = json.dumps(doc, default=str)
                            except:
                                doc_str = str(doc)
                            f.write(f"insert {table_name} {doc_str}\n")
                            
                    rprint(f"[bold green]OK: {len(rows)} documentos exportados a '{filename}'.[/bold green]")
                
                elif "redis" in db_type:
                    rprint("[bold yellow]INFO:[/bold yellow] Exportando claves como backup.")
                    success, keys_data, error = self.connector.execute_query(f"keys *")
                    if not success:
                        rprint(f"[bold red]ERROR:[/bold red] {error}")
                        return
                    
                    keys = keys_data if isinstance(keys_data, list) else []
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(f"// Dump de Redis\n")
                        count = 0
                        for key in keys:
                            s, val, e = self.connector.execute_query(f"get {key}")
                            if s and val is not None:
                                f.write(f"set {key} {val}\n")
                                count += 1
                    rprint(f"[bold green]OK: {count} claves exportadas a '{filename}'.[/bold green]")
                    
                elif "cassandra" in db_type:
                    success, data, error = self.connector.execute_query(f"SELECT * FROM {table_name}")
                    if not success:
                        rprint(f"[bold red]ERROR al consultar tabla:[/bold red] {error}")
                        return
                    
                    if not data or not data.get('rows'):
                        rprint(f"[bold yellow]INFO:[/bold yellow] La tabla '{table_name}' está vacía o no existe.")
                        return

                    columns = data['columns']
                    rows = data['rows']
                    
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(f"-- Dump de la tabla {table_name} en Cassandra\n")
                        for row in rows:
                            formatted_values = []
                            for val in row:
                                if val is None:
                                    formatted_values.append("NULL")
                                elif isinstance(val, (int, float)):
                                    formatted_values.append(str(val))
                                else:
                                    safe_val = str(val).replace("'", "''")
                                    formatted_values.append(f"'{safe_val}'")
                            
                            cols_str = ", ".join(columns)
                            vals_str = ", ".join(formatted_values)
                            f.write(f"INSERT INTO {table_name} ({cols_str}) VALUES ({vals_str});\n")
                    rprint(f"[bold green]OK: {len(rows)} registros exportados a '{filename}'.[/bold green]")

        except Exception as e:
            rprint(f"[bold red]ERROR al exportar a script:[/bold red] {e}")

    def _export_db(self, command: str):
        """Exporta la base de datos completa a un archivo .sql"""
        if not self.connector or not self.connector.is_connected:
            rprint("[bold red]ERROR:[/bold red] No hay conexión activa. [yellow]Conéctate a una BD antes de exportar.[/yellow]")
            return

        parts = command.split()
        if len(parts) < 2:
            rprint("[bold red]ERROR:[/bold red] Uso: export_db <archivo.sql>")
            return
            
        filename = parts[1]
        db_type = self.connector.get_type().lower()
        rprint(f"[bold blue]Exportando BD completa a '{filename}'...[/bold blue]")
        
        try:
            if self.mode == "rel":
                if "sqlite" in db_type:
                    # Usar iterdump
                    with open(filename, 'w', encoding='utf-8') as f:
                        for line in self.connector.connection.iterdump():
                            f.write(f"{line}\n")
                    rprint(f"[bold green]OK: Base de datos SQLite exportada a '{filename}'.[/bold green]")
                
                elif "postgres" in db_type:
                    import subprocess
                    env = os.environ.copy()
                    if hasattr(self.connector, 'password') and self.connector.password:
                        env['PGPASSWORD'] = self.connector.password
                        
                    cmd = [
                        "pg_dump",
                        "-h", self.connector.host,
                        "-p", str(self.connector.port),
                        "-U", self.connector.user,
                        "-d", self.connector.dbname,
                        "-f", filename
                    ]
                    rprint("[bold yellow]INFO:[/bold yellow] Usando pg_dump de sistema...")
                    try:
                        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
                        if result.returncode == 0:
                            rprint(f"[bold green]OK: Base de datos Postgres exportada a '{filename}'.[/bold green]")
                        else:
                            rprint(f"[bold red]ERROR pg_dump:[/bold red]\n{result.stderr}")
                    except FileNotFoundError:
                        rprint("[bold yellow]INFO:[/bold yellow] 'pg_dump' no encontrada. Intentando exportación básica en Python...")
                        success, tables, err = self.connector.get_tables()
                        if not success:
                            rprint(f"[bold red]ERROR al obtener tablas:[/bold red] {err}")
                            return
                        
                        with open(filename, 'w', encoding='utf-8') as f:
                            f.write(f"-- Backup básico de PostgreSQL para {self.connector.dbname}\n")
                            f.write(f"-- Generado por DBAdmin\n\n")
                            
                            for table in tables:
                                rprint(f"   [blue]Exportando tabla:[/blue] [white]{table}...[/white]")
                                # Escapamos el nombre de la tabla por seguridad
                                quoted_table = f'"{table}"'
                                
                                s, data, err = self.connector.execute_query(f"SELECT * FROM {quoted_table}")
                                if not s:
                                    rprint(f"   [bold red]ERROR en tabla {table}:[/bold red] {err}")
                                    f.write(f"-- ERROR al exportar tabla {table}: {err}\n")
                                    continue
                                    
                                if data and data.get('rows'):
                                    columns = data['columns']
                                    quoted_cols = [f'"{c}"' for c in columns]
                                    for row in data['rows']:
                                        formatted_values = []
                                        for val in row:
                                            if val is None:
                                                formatted_values.append("NULL")
                                            elif isinstance(val, (int, float)):
                                                formatted_values.append(str(val))
                                            else:
                                                safe_val = str(val).replace("'", "''")
                                                formatted_values.append(f"'{safe_val}'")
                                        cols_str = ", ".join(quoted_cols)
                                        vals_str = ", ".join(formatted_values)
                                        f.write(f"INSERT INTO {quoted_table} ({cols_str}) VALUES ({vals_str});\n")
                                    rprint(f"   [green]OK:[/green] {len(data['rows'])} filas exportadas.")
                                else:
                                    rprint(f"   [yellow]Aviso:[/yellow] Tabla vacía.")
                                    f.write(f"-- Tabla {table} sin datos\n")
                                f.write("\n")
                        rprint(f"[bold green]OK: Exportación básica completada a '{filename}'.[/bold green]")
                        
                elif "mysql" in db_type:
                    import subprocess
                    cmd = [
                        "mysqldump",
                        "-h", self.connector.host,
                        f"-P{self.connector.port}",
                        f"-u{self.connector.user}",
                        self.connector.database,
                        f"--result-file={filename}"
                    ]
                    if hasattr(self.connector, 'password') and self.connector.password:
                        cmd.append(f"-p{self.connector.password}")
                        
                    rprint("[bold yellow]INFO:[/bold yellow] Usando mysqldump de sistema...")
                    try:
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        if result.returncode == 0:
                            rprint(f"[bold green]OK: Base de datos MySQL exportada a '{filename}'.[/bold green]")
                        else:
                            rprint(f"[bold red]ERROR mysqldump:[/bold red]\n{result.stderr}")
                    except FileNotFoundError:
                        rprint("[bold yellow]INFO:[/bold yellow] 'mysqldump' no encontrada. Intentando exportación básica en Python...")
                        success, tables, err = self.connector.get_tables()
                        if not success:
                            rprint(f"[bold red]ERROR al obtener tablas:[/bold red] {err}")
                            return
                            
                        with open(filename, 'w', encoding='utf-8') as f:
                            f.write(f"-- Backup básico de MySQL para {self.connector.database}\n")
                            f.write(f"-- Generado por DBAdmin\n\n")
                            f.write("SET FOREIGN_KEY_CHECKS = 0;\n\n")
                            
                            for table in tables:
                                rprint(f"   [blue]Exportando tabla:[/blue] [white]{table}...[/white]")
                                quoted_table = f"`{table}`"
                                
                                # Intentar obtener el CREATE TABLE
                                s, crt_data, err = self.connector.execute_query(f"SHOW CREATE TABLE {quoted_table}")
                                if s and crt_data and crt_data.get('rows'):
                                    f.write(f"DROP TABLE IF EXISTS {quoted_table};\n")
                                    f.write(f"{crt_data['rows'][0][1]};\n\n")
                                
                                # Exportar datos
                                s, data, err = self.connector.execute_query(f"SELECT * FROM {quoted_table}")
                                if not s:
                                    rprint(f"   [bold red]ERROR en tabla {table}:[/bold red] {err}")
                                    continue
                                    
                                if data and data.get('rows'):
                                    columns = data['columns']
                                    quoted_cols = [f"`{c}`" for c in columns]
                                    for row in data['rows']:
                                        formatted_values = []
                                        for val in row:
                                            if val is None:
                                                formatted_values.append("NULL")
                                            elif isinstance(val, (int, float)):
                                                formatted_values.append(str(val))
                                            else:
                                                safe_val = str(val).replace("'", "''").replace("\\", "\\\\")
                                                formatted_values.append(f"'{safe_val}'")
                                        cols_str = ", ".join(quoted_cols)
                                        vals_str = ", ".join(formatted_values)
                                        f.write(f"INSERT INTO {quoted_table} ({cols_str}) VALUES ({vals_str});\n")
                                    rprint(f"   [green]OK:[/green] {len(data['rows'])} filas exportadas.")
                                else:
                                    rprint(f"   [yellow]Aviso:[/yellow] Tabla vacía.")
                                f.write("\n")
                            f.write("SET FOREIGN_KEY_CHECKS = 1;\n")
                        rprint(f"[bold green]OK: Exportación básica completada a '{filename}'.[/bold green]")
                        
            else:
                # NoSQL: exportar todas las colecciones/claves
                success, collections, err = self.connector.get_tables()
                if not success:
                    rprint(f"[bold red]ERROR al obtener colecciones:[/bold red] {err}")
                    return
                
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"// Backup completo de {db_type}\n")
                    
                    for coll in collections:
                        f.write(f"\n// Colección/Tabla: {coll}\n")
                        if "mongodb" in db_type:
                            s, data, e = self.connector.execute_query(f"find {coll} {{}}")
                            if s and data and data.get('rows'):
                                import json
                                rows = data.get('rows', [])
                                columns = data.get('columns', [])
                                for row in rows:
                                    doc = {columns[i]: row[i] for i in range(len(columns)) if row[i] != ""}
                                    try:
                                        doc_str = json.dumps(doc, default=str)
                                    except:
                                        doc_str = str(doc)
                                    f.write(f"insert {coll} {doc_str}\n")
                                    
                        elif "cassandra" in db_type:
                            s, data, e = self.connector.execute_query(f"SELECT * FROM {coll}")
                            if s and data and data.get('rows'):
                                columns = data['columns']
                                for row in data['rows']:
                                    formatted_values = []
                                    for val in row:
                                        if val is None:
                                            formatted_values.append("NULL")
                                        elif isinstance(val, (int, float)):
                                            formatted_values.append(str(val))
                                        else:
                                            safe_val = str(val).replace("'", "''")
                                            formatted_values.append(f"'{safe_val}'")
                                    
                                    cols_str = ", ".join(columns)
                                    vals_str = ", ".join(formatted_values)
                                    f.write(f"INSERT INTO {coll} ({cols_str}) VALUES ({vals_str});\n")
                                    
                    if "redis" in db_type:
                        f.write("\n// Backup Redis\n")
                        s, keys_data, e = self.connector.execute_query("keys *")
                        if s:
                            keys = keys_data if isinstance(keys_data, list) else []
                            for key in keys:
                                ss, val, ee = self.connector.execute_query(f"get {key}")
                                if ss and val is not None:
                                    f.write(f"set {key} {val}\n")
                                    
                rprint(f"[bold green]OK: Base de datos NoSQL exportada a '{filename}'.[/bold green]")
                
        except Exception as e:
            rprint(f"[bold red]ERROR al exportar BD:[/bold red] {e}")

    def _insert(self, command: str):
        """Ejecutar INSERT"""
        success, data, error = self.connector.execute_query(command)
        if success:
            print("✅ Registro insertado correctamente")
        else:
            print(f"❌ Error: {error}")

    def _update(self, command: str):
        """Ejecutar UPDATE"""
        success, data, error = self.connector.execute_query(command)
        if success:
            print("✅ Registro(s) actualizado(s) correctamente")
        else:
            print(f"❌ Error: {error}")

    def _delete(self, command: str):
        """Ejecutar DELETE"""
        success, data, error = self.connector.execute_query(command)
        if success:
            print("✅ Registro(s) eliminado(s) correctamente")
        else:
            print(f"❌ Error: {error}")

    def _create_table(self, command: str):
        """Ejecutar CREATE TABLE"""
        success, data, error = self.connector.execute_query(command)
        if success:
            print("✅ Tabla creada correctamente")
        else:
            print(f"❌ Error: {error}")

    def _drop_table(self, command: str):
        """Ejecutar DROP TABLE"""
        success, data, error = self.connector.execute_query(command)
        if success:
            print("✅ Tabla eliminada correctamente")
        else:
            print(f"❌ Error: {error}")

    def _show_tables(self):
        """Listar todas las tablas"""
        success, data, error = self.connector.get_tables()
        if success:
            if data:
                table_list = Text()
                for table in data:
                    table_list.append(f"  * {table}\n", style="cyan")
                
                self.console.print(Panel(
                    table_list, 
                    title="[bold white]TABLAS ENCONTRADAS[/bold white]", 
                    subtitle=f"[yellow]Total: {len(data)}[/yellow]",
                    expand=False
                ))
            else:
                rprint("[bold yellow]INFO: No hay tablas en la base de datos.[/bold yellow]")
        else:
            rprint(f"[bold red]ERROR:[/bold red] [white]{error}[/white]")

    def _execute_nosql_query(self, command: str):
        """Ejecuta una consulta NoSQL y muestra los resultados"""
        success, data, error = self.connector.execute_query(command)
        if success:
            if data and 'columns' in data and data['columns']:
                self.last_results = data
                self.formatter.print_table(data['columns'], data['rows'])
                rprint(f"\n[bold cyan]INFO: Total:[/bold cyan] [white]{len(data['rows'])} fila(s)/documento(s)[/white]")
            elif data and 'affected_rows' in data:
                rprint(f"[bold green]OK: Éxito:[/bold green] [white]{data['affected_rows']} fila(s)/documento(s) afectada(s)[/white]")
            elif isinstance(data, list):
                # Formateo simple para listas planas (ej: KEYS en Redis)
                self.formatter.print_table(["Resultados"], [[str(item)] for item in data])
                rprint(f"\n[bold cyan]INFO: Total:[/bold cyan] [white]{len(data)} resultado(s)[/white]")
            elif isinstance(data, dict):
                # Formateo para diccionarios simples
                self.formatter.print_table(["Clave", "Valor"], [[str(k), str(v)] for k, v in data.items()])
            elif data is not None:
                rprint(f"[bold green]Resultado:[/bold green] [white]{data}[/white]")
            else:
                rprint("[bold green]OK: Comando ejecutado correctamente sin devolver datos.[/bold green]")
        else:
            rprint(f"[bold red]ERROR NOSQL:[/bold red] [white]{error}[/white]")
    
    def _handle_safebridge_validation(self, command: str):
        """Maneja el comando de validación externa de la API de Iker"""
        parts = shlex.split(command)
        # Sintaxis esperada: validate backup <ruta> <motor> <nombre_bd>
        if len(parts) < 5:
            rprint("[bold red]❌ Sintaxis incorrecta.[/bold red] Uso: `validate backup <ruta_archivo> <motor> <nombre_base_datos>`")
            rprint("Ejemplo: [dim]validate backup /backups/data.sql postgres tienda_db[/dim]")
            return

        path_backup = parts[2]
        engine_type = parts[3]
        db_name = parts[4]

        client = SafeBridgeClient()
        success, result = client.validar_backup(path_backup, engine_type, db_name)

        if success:
            tables_validated = int(result.get("tables_validated", 0) or 0)
            warnings = result.get("warnings", []) or []
            critical_errors = result.get("critical_errors", []) or []
            integrity_valid = bool(result.get("integrity_valid")) and tables_validated > 0 and not critical_errors

            rprint("\n[bold green]📊 REPORTE DE INTEGRIDAD EN DOCKER SANDBOX (SafeBridge API)[/bold green]")
            
            headers = ["Criterio de Validación", "Resultado / Valor"]
            estado_int = "[bold green]✔️ PASA CONTROL (VÁLIDO)[/bold green]" if integrity_valid else "[bold red]❌ FALLIDO (DAÑADO)[/bold red]"
            
            rows = [
                ["Estado de Integridad", estado_int],
                ["Tablas Restauradas y Validadas", str(tables_validated)],
                ["Tiempo de Ejecución Docker", f"{result.get('execution_time_seconds', 0)} seg"],
                ["Alertas detectadas", str(len(warnings))],
                ["Errores Críticos", str(len(critical_errors))]
            ]
            self.formatter.print_table(headers, rows)
            
            if warnings:
                rprint(f"[bold yellow]⚠️ Advertencias:[/bold yellow] {warnings}")
            if critical_errors:
                rprint(f"[bold red]🚨 Errores Críticos del Sandbox:[/bold red] {critical_errors}")
            elif tables_validated == 0 and warnings:
                rprint("[bold red]🚨 La validación no restauró tablas, aunque el sandbox la marcó como válida.[/bold red]")
                rprint("[yellow]Revisa el backend SafeBridge: el warning indica que MySQL intentó usar el socket local en vez de una conexión de contenedor.[/yellow]")
        else:
            rprint(f"[bold red]❌ Error en la Validación Externa:[/bold red] {result}")

    def _migrate(self, command: str):
        """Ejecuta una migración de base de datos de origen a destino (ETL)"""
        parts = shlex.split(command)
        if len(parts) < 4:
            rprint("[bold red]❌ Sintaxis incorrecta.[/bold red] Uso: `migrate <archivo_origen> <motor_destino> <archivo_salida> [--simulacion]`")
            rprint("Ejemplo: [dim]migrate test.db postgres dump_postgres.sql[/dim]")
            return
            
        archivo_origen = parts[1]
        motor_destino = parts[2]
        archivo_salida = parts[3]
        
        simulacion = False
        if len(parts) > 4 and parts[4].lower() in ["--simulacion", "-s", "--sim", "simulacion"]:
            simulacion = True
            
        if not os.path.exists(archivo_origen):
            rprint(f"[bold red]❌ Error:[/bold red] El archivo de origen '{archivo_origen}' no existe.")
            return
            
        # 1. DETECTAR EL TIPO DE BASE DE DATOS DE ORIGEN
        rprint(f"[bold blue][ETL][/bold blue] Detectando tipo de base de datos de origen para '{archivo_origen}'...")
        tipo_origen, msg_deteccion, _ = DetectorBaseDatos.detectar(archivo_origen, os.path.basename(archivo_origen))
        
        if tipo_origen == "Desconocido":
            rprint(f"[bold red]❌ Error de detección:[/bold red] {msg_deteccion}")
            return
            
        rprint(f"[bold green]✓ Origen detectado:[/bold green] [white]{tipo_origen}[/white] ({msg_deteccion})")
        
        # 2. CONECTAR ORIGEN Y DESTINO
        try:
            rprint(f"[bold blue][ETL][/bold blue] Cargando conector de origen...")
            origen = ConectorOrigen(archivo_origen, tipo_origen)
            if not origen.tablas:
                rprint("[bold red]❌ Error:[/bold red] El origen no contiene ninguna tabla legible.")
                return
            rprint(f"[bold green]✓ Conector de origen listo.[/bold green] Encontradas {len(origen.tablas)} tablas.")
            
            rprint(f"[bold blue][ETL][/bold blue] Inicializando cargador para motor destino '{motor_destino}'...")
            destino = CargadorDestino(motor_destino)
            destino.tabla_a_esquema = origen.tabla_a_esquema
        except Exception as e:
            rprint(f"[bold red]❌ Error de inicialización ETL:[/bold red] {e}")
            return
            
        # 3. CREAR ESTRUCTURA EN EL CARGADOR TEMPORAL
        try:
            rprint(f"[bold blue][ETL][/bold blue] Creando estructura de tablas en base intermedia...")
            creadas = destino.crear_estructura(origen.esquema, origen.tabla_a_esquema)
            rprint(f"[bold green]✓ Creadas {creadas} tablas en base intermedia.[/bold green]")
        except Exception as e:
            rprint(f"[bold red]❌ Error al crear estructura:[/bold red] {e}")
            
        # 4. MIGRAR DATOS POR BLOQUES (CHUNKS)
        rprint(f"[bold blue][ETL][/bold blue] Iniciando extracción y carga por bloques (chunk size = 10000)...")
        if simulacion:
            rprint("[bold yellow]⚠️ MODO SIMULACIÓN ACTIVO (No se guardarán datos reales)[/bold yellow]")
            
        metricas = {'extraidos': 0, 'cargados': 0, 'errores': 0, 'tablas_ok': 0}
        total_tablas = len(origen.tablas)
        
        for idx, tabla in enumerate(origen.tablas):
            rprint(f"   [{idx+1}/{total_tablas}] Procesando tabla [cyan]{tabla}[/cyan]...")
            
            try:
                filas_tabla_orig = 0
                for chunk_df in origen.extraer_datos_chunked(tabla, chunksize=10000):
                    filas_chunk = len(chunk_df)
                    metricas['extraidos'] += filas_chunk
                    filas_tabla_orig += filas_chunk
                    
                    if not chunk_df.empty:
                        chunk_df = MapeadorDatos.limpiar_dataframe(chunk_df)
                        
                        if not simulacion:
                            cargados = destino.cargar_tabla(tabla, chunk_df)
                        else:
                            cargados = filas_chunk
                            
                        metricas['cargados'] += cargados
                        
                rprint(f"   [green]✓[/green] Tabla [cyan]{tabla}[/cyan] completada ({filas_tabla_orig} registros).")
                metricas['tablas_ok'] += 1
            except Exception as e:
                metricas['errores'] += 1
                rprint(f"   [bold red]❌ Error en tabla {tabla}:[/bold red] {e}")
                
        # 5. MIGRAR VISTAS, TRIGGERS Y DEMÁS OBJETOS NO-TABULARES
        rprint(f"[bold blue][ETL][/bold blue] Migrando vistas, triggers y otros objetos de base de datos...")
        vistas_ok = 0
        triggers_ok = 0
        indices_ok = 0
        procs_ok = 0
        funcs_ok = 0
        
        if hasattr(origen, 'vistas') and origen.vistas:
            vistas_ok = destino.crear_vistas(origen.vistas)
        if hasattr(origen, 'triggers') and origen.triggers:
            triggers_ok = destino.crear_triggers(origen.triggers)
        if hasattr(origen, 'indices') and origen.indices:
            indices_ok = destino.crear_indices(origen.indices)
        if hasattr(origen, 'procedimientos') and origen.procedimientos:
            procs_ok = destino.crear_procedimientos(origen.procedimientos)
        if hasattr(origen, 'funciones') and origen.funciones:
            funcs_ok = destino.crear_funciones(origen.funciones)
            
        rprint(f"   Objetos procesados: Vistas: {vistas_ok}, Triggers: {triggers_ok}, Índices: {indices_ok}, Proc: {procs_ok}, Func: {funcs_ok}")
        
        # 6. EXPORTAR AL ARCHIVO DE SALIDA
        rprint(f"[bold blue][ETL][/bold blue] Generando archivo de exportación para '{motor_destino}'...")
        try:
            export_val, ext, mimetype, es_binario = destino.generar_export(motor_destino)
            
            salida_dir = os.path.dirname(os.path.abspath(archivo_salida))
            if salida_dir and not os.path.exists(salida_dir):
                os.makedirs(salida_dir, exist_ok=True)
                
            if es_binario:
                import shutil
                shutil.copy(export_val, archivo_salida)
            else:
                with open(archivo_salida, 'w', encoding='utf-8') as f:
                    f.write(export_val)
                    
            rprint(f"[bold green]🎉 ¡MIGRACIÓN COMPLETADA EXITOSAMENTE![/bold green]")
            
            headers = ["Métrica / Resumen", "Resultado"]
            rows = [
                ["Tablas Procesadas con Éxito", f"{metricas['tablas_ok']} / {total_tablas}"],
                ["Registros Extraídos", str(metricas['extraidos'])],
                ["Registros Cargados", str(metricas['cargados'])],
                ["Errores en Tablas", str(metricas['errores'])],
                ["Vistas Procesadas", str(vistas_ok)],
                ["Triggers Procesados", str(triggers_ok)],
                ["Índices Procesados", str(indices_ok)],
                ["Archivo Guardado En", archivo_salida]
            ]
            self.formatter.print_table(headers, rows)
            
        except Exception as e:
            rprint(f"[bold red]❌ Error al exportar archivo final:[/bold red] {e}")