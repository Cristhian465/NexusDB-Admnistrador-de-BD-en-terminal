"""
Módulo REPL - Read-Eval-Print Loop
Bucle principal que lee comandos y los ejecuta
"""

import sys
import os
import csv
import shlex

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

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

# ── Módulos de extensión Nexus-DB ──────────────────────────────────────────
from features.ai_helper import sugerir_sql
from features.panel_rendimiento import mostrar_panel
from features.programador_tareas import ProgramadorTareas
from features.usuarios import GestorUsuarios
from features.comparador import comparar_bds, revisar_seguridad
from features.ux_mejoras import (
    emoji_motor, mostrar_sugerencia, expandir_abreviacion,
    COMPLETIONS_EXTRA, exito, error as ux_error, advertencia, info, conexion,
)
from features.asistente_voz import resumir_resultado, es_palabra_salir
from features.cerebro_sql import generar_sql, disponible as ia_disponible
from features.bookmarks import BookmarkManager
from features.erd_generator import generar_diagrama

class _NexusCompleter(Completer):
    """Proveedor de autocompletado TAB para prompt_toolkit."""

    def __init__(self, repl_instance):
        self._repl = repl_instance

    def get_completions(self, document, complete_event):
        import re
        # Extraer la última palabra escrita (puede contener _, -, etc)
        word_before_cursor = document.get_word_before_cursor(pattern=re.compile(r'[\w\-]+'))
        if not word_before_cursor:
            return
            
        options = self._repl._get_completions(document.text_before_cursor)
        # Usar un set para evitar duplicados
        for opt in sorted(set(options)):
            if opt.lower().startswith(word_before_cursor.lower()):
                yield Completion(opt, start_position=-len(word_before_cursor))


class REPL:
    """Bucle principal de la aplicación"""

    def __init__(self, mode='rel'):
        self.running = True
        self.mode = mode
        self.console = Console()
        self.connector = None
        self.connector2 = None          # Segundo conector para diff
        self.formatter = TableFormatter()
        self.last_results = None        # Almacena el resultado del último SELECT
        self.in_transaction = False
        self._schema_cache = {}

        # Módulos de extensión
        self.gestor_usuarios = GestorUsuarios()
        self.programador = ProgramadorTareas(repl_execute_fn=self.execute)
        self.voz = None                  # NexusVoice (carga perezosa)
        self.bookmark_mgr = BookmarkManager()

        # prompt_toolkit: historial de comandos y autocompletado
        history_path = os.path.expanduser('~/.nexusdb_history')
        self._history   = FileHistory(history_path)
        self._completer = _NexusCompleter(self)
        self._pt_style  = Style.from_dict({"prompt": "bold cyan"})
        self._pt_kb     = self._build_keybindings()

        self._setup_autocomplete()  # fallback readline (no-op si prompt_toolkit funciona)

    def _get_prompt(self):
        """Genera el prompt dinámicamente según el estado de la conexión."""
        base = "nexus-db"
        user_prefix = f"{self.gestor_usuarios.usuario_actual}@" if self.gestor_usuarios.usuario_actual else ""
        if self.connector and self.connector.is_connected:
            db_type = self.connector.get_type().lower()
            db_info = self.connector.get_info()
            db_name = os.path.basename(db_info)
            em = emoji_motor(db_type)
            tx_indicator = "[bold red]TX[/bold red] | " if self.in_transaction else ""
            return f"[{tx_indicator}{base} | {user_prefix}{em} {db_type}: {db_name}] > "
        return f"[{base} | {user_prefix}📂 desconectado] > "

    def _build_keybindings(self):
        """Define atajos de teclado adicionales para prompt_toolkit."""
        kb = KeyBindings()

        @kb.add("c-l")          # Ctrl+L → limpiar pantalla
        def _ctrl_l(event):
            os.system("cls" if os.name == "nt" else "clear")
            event.app.renderer.reset()
            event.app.invalidate()

        return kb

    def _setup_autocomplete(self):
        """Fallback readline — solo actúa si prompt_toolkit no está disponible."""
        try:
            import readline
            delims = readline.get_completer_delims()
            readline.set_completer_delims(delims.replace(' ', '').replace('\t', ''))
            readline.set_completer(self._completer_readline)
            readline.parse_and_bind("tab: complete")
        except Exception:
            pass

    def _completer_readline(self, text, state):
        """Completer para readline (fallback en sistemas sin prompt_toolkit)."""
        try:
            words = text.split()
            last_word = words[-1] if words else text
            options = self._get_completions(text)
            matches = sorted(list(set([o for o in options if o.lower().startswith(last_word.lower())])))
            return matches[state] if state < len(matches) else None
        except Exception:
            return None

    def _get_completions(self, text: str) -> list:
        """Obtiene una lista de palabras sugeridas basadas en el texto actual"""
        keywords = [
            "SELECT", "FROM", "WHERE", "INSERT", "INTO", "VALUES", "UPDATE", "SET", 
            "DELETE", "JOIN", "ON", "AND", "OR", "LIMIT", "ORDER BY", "GROUP BY", 
            "CREATE TABLE", "DROP TABLE", "SHOW TABLES", "BEGIN", "COMMIT", "ROLLBACK",
            "FIND", "GET", "DEL", "KEYS", "SHOW COLLECTIONS", "SHOW KEYS"
        ]
        custom = [
            "connect", "disconnect", "status", "exit", "help", "panel", 
            "search", "bookmark", "generate_erd", "export", "import", 
            "migrate", "validate backup"
        ] + COMPLETIONS_EXTRA

        tables = []
        if self.connector and self.connector.is_connected:
            try:
                success, tbl_list, _ = self.connector.get_tables()
                if success:
                    tables = tbl_list
            except Exception:
                pass

        columns = []
        text_lower = text.lower()
        if tables:
            for t in tables:
                # Si la tabla se menciona en el comando, sugerimos sus columnas
                if t.lower() in text_lower:
                    if t not in self._schema_cache:
                        db_type = self.connector.get_type().lower()
                        query = f"SELECT * FROM {t} LIMIT 0"
                        if "postgres" in db_type:
                            query = f'SELECT * FROM "{t}" LIMIT 0'
                        elif "mysql" in db_type:
                            query = f"SELECT * FROM `{t}` LIMIT 0"
                        
                        s, data, _ = self.connector.execute_query(query)
                        if s and data and data.get("columns"):
                            self._schema_cache[t] = data["columns"]
                            
                    columns.extend(self._schema_cache.get(t, []))

        return keywords + custom + tables + columns

    def _clear_screen(self):
        """Limpia la pantalla de la terminal."""
        os.system('cls' if os.name == 'nt' else 'clear')

    def run(self):
        """Ejecuta el bucle principal usando prompt_toolkit para TAB y historial."""
        while self.running:
            try:
                current_prompt = self._get_prompt()

                command = pt_prompt(
                    current_prompt,
                    completer=self._completer,
                    history=self._history,
                    key_bindings=self._pt_kb,
                    style=self._pt_style,
                    complete_while_typing=False,   # solo al presionar TAB
                ).strip()

                if not command:
                    continue

                if command.lower() in ('cls', 'clear'):
                    self._clear_screen()
                    continue

                try:
                    self.execute(command)
                except Exception as e:
                    rprint(f"\n[bold red]ERROR de ejecución:[/bold red] [white]{e}[/white]")
                    rprint("[yellow]La aplicación sigue activa. Intenta de nuevo.[/yellow]\n")

            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                rprint("\n[yellow]Usa 'exit' para salir. Ctrl+L para limpiar pantalla.[/yellow]")
                continue

    def execute(self, command: str):
        """Ejecuta un comando según su tipo"""
        # Expandir abreviaciones antes de procesar
        command = expandir_abreviacion(command)
        cmd = command.lower().strip()

        # ── Comandos sin autenticación requerida ───────────────────────────────
        if cmd == "exit":
            self._exit()
            return
        elif cmd == "help":
            self._help()
            return

        # ── Control por voz (NexusVoice) ───────────────────────────────────────
        elif cmd in ("voz", "voice", "voz on", "voice on"):
            self._handle_voice_loop()
            return
        elif cmd in ("voz once", "voice once"):
            self._handle_voice_once()
            return
        elif cmd.startswith("voz engine") or cmd.startswith("voice engine"):
            self._handle_voice_engine(command)
            return
        elif cmd.startswith("voz test") or cmd.startswith("voice test"):
            self._handle_voice_test(command)
            return

        # ── Autenticación / usuarios ───────────────────────────────────────────
        elif cmd.startswith("login") or cmd == "logout" or cmd == "whoami" or cmd.startswith("users"):
            self._handle_auth(command)
            return

        # ── Verificar permiso de rol (si hay sesión activa) ───────────────────
        if not self.gestor_usuarios.tiene_permiso(command):
            rprint(f"[bold red]❌ Permiso denegado:[/bold red] el rol '[yellow]{self.gestor_usuarios.rol_actual}[/yellow]' "
                   f"no puede ejecutar '{cmd.split()[0]}'.")
            return

        # ── Auditar el comando ─────────────────────────────────────────────────
        self.gestor_usuarios.registrar_comando(command)

        # ── Verificación de seguridad para comandos peligrosos ─────────────────
        if not revisar_seguridad(command):
            return

        # ── Nuevos módulos ─────────────────────────────────────────────────────
        if cmd.startswith("ai"):
            self._handle_ai(command)
        elif cmd == "panel":
            self._handle_panel()
        elif cmd.startswith("schedule"):
            self._handle_schedule(command)
        elif cmd.startswith("diff"):
            self._handle_diff(command)
        elif cmd.startswith("connect2"):
            self._connect2(command)
        
        # ── Transacciones ──────────────────────────────────────────────────────
        elif cmd in ("begin", "commit", "rollback"):
            self._handle_transaction(cmd)
            return
            
        # ── Búsqueda Global, Bookmarks, ERD ────────────────────────────────────
        elif cmd.startswith("search "):
            self._handle_search(command)
            return
        elif cmd.startswith("bookmark"):
            self._handle_bookmark(command)
            return
        elif cmd == "generate_erd":
            self._handle_erd()
            return

        # ── Comandos existentes ────────────────────────────────────────────────
        elif cmd.startswith("validate backup"):
            self._handle_safebridge_validation(command)
        elif cmd.startswith("migrate"):
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
                mostrar_sugerencia("connect")
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

    # ── Handlers de nuevos módulos ─────────────────────────────────────────────

    def _handle_transaction(self, cmd: str):
        if not self.connector or not self.connector.is_connected:
            rprint("[bold red]ERROR:[/bold red] No hay conexión activa.")
            return
            
        if self.mode != "rel":
            rprint("[bold yellow]INFO:[/bold yellow] Transacciones explícitas solo en modo relacional.")
            return
            
        success, _, err = self.connector.execute_query(cmd)
        if success:
            if cmd == "begin":
                self.in_transaction = True
                rprint("[bold green]OK: Transacción iniciada.[/bold green]")
            elif cmd == "commit":
                self.in_transaction = False
                rprint("[bold green]OK: Transacción confirmada (COMMIT).[/bold green]")
            elif cmd == "rollback":
                self.in_transaction = False
                rprint("[bold yellow]OK: Transacción revertida (ROLLBACK).[/bold yellow]")
        else:
            # Si falla un commit o rollback (ej: no hay transacción activa),
            # limpiamos el indicador de todas formas para no trabar el prompt.
            if cmd in ("commit", "rollback"):
                self.in_transaction = False
            rprint(f"[bold red]ERROR en {cmd.upper()}:[/bold red] {err}")

    def _handle_search(self, command: str):
        if not self.connector or not self.connector.is_connected:
            rprint("[bold red]ERROR:[/bold red] No hay conexión activa.")
            return
            
        import shlex
        try:
            parts = shlex.split(command)
        except ValueError:
            parts = command.split()
            
        if len(parts) < 2:
            rprint("[yellow]Uso: search \"texto\"[/yellow]")
            return
            
        term = parts[1]
        
        if self.mode != "rel":
            rprint("[yellow]Búsqueda global soportada en modo relacional.[/yellow]")
            return

        s, tables, err = self.connector.get_tables()
        if not s or not tables:
            rprint("[yellow]No hay tablas o error al leerlas.[/yellow]")
            return
            
        rprint(f"[bold blue]🔍 Buscando '{term}' en {len(tables)} tablas...[/bold blue]")
        
        safe_term = term.replace("'", "''")
        match_count = 0
        db_type = self.connector.get_type().lower()
        
        for table in tables:
            query_col = f"SELECT * FROM {table} LIMIT 0"
            if "postgres" in db_type:
                query_col = f'SELECT * FROM "{table}" LIMIT 0'
            elif "mysql" in db_type:
                query_col = f"SELECT * FROM `{table}` LIMIT 0"
                
            s, data, err = self.connector.execute_query(query_col)
            if not s or not data or not data.get("columns"):
                continue
            
            columns = data["columns"]
            where_clauses = []
            
            for col in columns:
                if "postgres" in db_type:
                    where_clauses.append(f'CAST("{col}" AS TEXT) ILIKE \'%{safe_term}%\'')
                elif "mysql" in db_type:
                    where_clauses.append(f"`{col}` LIKE '%{safe_term}%'")
                else:
                    where_clauses.append(f"CAST(\"{col}\" AS TEXT) LIKE '%{safe_term}%'")
            
            if not where_clauses:
                continue
                
            where_sql = " OR ".join(where_clauses)
            
            query = f"SELECT * FROM {table} WHERE {where_sql} LIMIT 50"
            if "postgres" in db_type:
                query = f'SELECT * FROM "{table}" WHERE {where_sql} LIMIT 50'
            elif "mysql" in db_type:
                query = f"SELECT * FROM `{table}` WHERE {where_sql} LIMIT 50"
                
            s, data, err = self.connector.execute_query(query)
            if s and data and data.get("rows"):
                rprint(f"\n[bold green]✅ Coincidencias en la tabla '{table}' ({len(data['rows'])} filas):[/bold green]")
                self.formatter.print_table(data["columns"], data["rows"])
                match_count += 1
                
        if match_count == 0:
            rprint("[yellow]No se encontraron resultados en ninguna tabla.[/yellow]")

    def _handle_bookmark(self, command: str):
        parts = command.strip().split(None, 2)
        if len(parts) < 2:
            rprint("[yellow]Uso: bookmark list | bookmark save <alias> \"<sql>\" | bookmark run <alias> | bookmark delete <alias>[/yellow]")
            return
            
        action = parts[1].lower()
        
        if action == "list":
            self.bookmark_mgr.list_all()
        elif action == "delete" and len(parts) >= 3:
            if self.bookmark_mgr.delete(parts[2]):
                exito(f"Bookmark '{parts[2]}' eliminado.")
            else:
                rprint(f"[red]No se encontró el bookmark '{parts[2]}'.[/red]")
        elif action == "save" and len(parts) >= 3:
            import shlex
            subparts = shlex.split(parts[2])
            if len(subparts) >= 2:
                alias = subparts[0]
                sql = subparts[1]
                if self.bookmark_mgr.add(alias, sql):
                    exito(f"Bookmark '{alias}' guardado.")
            else:
                rprint("[yellow]Uso: bookmark save <alias> \"<sql>\"[/yellow]")
        elif action == "run" and len(parts) >= 3:
            alias = parts[2]
            sql = self.bookmark_mgr.get(alias)
            if sql:
                rprint(f"[cyan]Ejecutando '{alias}':[/cyan] [white]{sql}[/white]")
                self.execute(sql)
            else:
                rprint(f"[red]No se encontró el bookmark '{alias}'.[/red]")
        else:
            rprint("[red]Acción desconocida o parámetros incompletos.[/red]")

    def _handle_erd(self):
        if not self.connector or not self.connector.is_connected:
            rprint("[bold red]ERROR:[/bold red] No hay conexión activa.")
            return
        if self.mode != "rel":
            rprint("[yellow]Los diagramas ERD solo están soportados en modo relacional.[/yellow]")
            return
            
        rprint("[blue]Generando diagrama ERD...[/blue]")
        mermaid_code = generar_diagrama(self.connector)
        
        if not mermaid_code:
            rprint("[yellow]No se pudo generar el diagrama. ¿Hay tablas en la BD?[/yellow]")
            return
            
        filename = "diagrama_erd.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write("```mermaid\n")
            f.write(mermaid_code)
            f.write("\n```\n")
            
        rprint(f"[bold green]✅ Diagrama guardado en '{filename}'.[/bold green]")
        rprint("[dim]Puedes visualizarlo con extensiones de Markdown o PlantUML/Mermaid en tu editor.[/dim]")

    def _handle_ai(self, command: str):
        """Asistente de lenguaje natural → SQL."""
        # Extraer el texto entre comillas o sin ellas
        import re as _re
        m = _re.match(r'^ai\s+"(.+)"$', command.strip(), _re.IGNORECASE)
        if not m:
            m = _re.match(r"^ai\s+'(.+)'$", command.strip(), _re.IGNORECASE)
        if not m:
            m = _re.match(r'^ai\s+(.+)$', command.strip(), _re.IGNORECASE)

        if not m:
            rprint("[yellow]Uso: ai \"<texto en español>\"[/yellow]")
            mostrar_sugerencia("ai")
            return

        texto = m.group(1).strip()
        sql, fuente = generar_sql(texto, self.connector, self.mode)

        if not sql:
            rprint(f"[yellow]💡 No pude generar SQL para esa petición.[/yellow]")
            mostrar_sugerencia("ai")
            return

        etiqueta = "🧠 IA (Claude)" if fuente == "ia" else "🔤 patrón"
        rprint(f"\n[bold cyan]💡 SQL sugerido ({etiqueta}):[/bold cyan] [white]{sql}[/white]")

        if not self.connector or not self.connector.is_connected:
            rprint("[dim]Conéctate a una BD para ejecutar la consulta.[/dim]")
            return

        try:
            resp = input("¿Ejecutar? (s/n): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            resp = "n"

        if resp == "s":
            self.execute(sql)

    def _handle_panel(self):
        """Muestra el panel de rendimiento del motor activo."""
        mostrar_panel(self.connector)

    def _handle_schedule(self, command: str):
        """Gestiona tareas programadas."""
        parts = command.strip().split(None, 1)
        if len(parts) < 2:
            rprint("[yellow]Uso: schedule add <cmd> at HH:MM | schedule add <cmd> every N hours | schedule list | schedule cancel <id>[/yellow]")
            mostrar_sugerencia("schedule")
            return

        sub = parts[1].strip()

        if sub == "list":
            self.programador.listar()
            return

        if sub.startswith("cancel "):
            try:
                tid = int(sub.split()[1])
            except (IndexError, ValueError):
                rprint("[red]Uso: schedule cancel <id>[/red]")
                return
            if self.programador.cancelar(tid):
                exito(f"Tarea #{tid} cancelada.")
            else:
                rprint(f"[red]No se encontró la tarea #{tid}.[/red]")
            return

        if sub.startswith("add "):
            resto = sub[4:].strip()

            # schedule add <cmd> every N hours
            import re as _re
            m = _re.search(r'^(.+?)\s+every\s+(\d+)\s+hours?$', resto, _re.IGNORECASE)
            if m:
                cmd_t, horas = m.group(1).strip().strip('"'), int(m.group(2))
                tid = self.programador.agregar_every(cmd_t, horas)
                exito(f"Tarea #{tid} programada: '{cmd_t}' cada {horas}h.")
                return

            # schedule add <cmd> at HH:MM
            m = _re.search(r'^(.+?)\s+at\s+(\d{1,2}:\d{2})$', resto, _re.IGNORECASE)
            if m:
                cmd_t, hora = m.group(1).strip().strip('"'), m.group(2)
                tid = self.programador.agregar_at(cmd_t, hora)
                exito(f"Tarea #{tid} programada: '{cmd_t}' a las {hora} cada día.")
                return

            rprint("[red]Formato no reconocido.[/red]")
            mostrar_sugerencia("schedule")
            return

        rprint("[red]Subcomando desconocido. Usa: schedule add|list|cancel[/red]")

    def _handle_auth(self, command: str):
        """Gestiona login, logout, whoami y gestión de usuarios."""
        parts = command.strip().split()
        sub = parts[0].lower()

        if sub == "login":
            if len(parts) < 3:
                rprint("[yellow]Uso: login <usuario> <contraseña>[/yellow]")
                return
            nombre, pwd = parts[1], parts[2]
            if self.gestor_usuarios.login(nombre, pwd):
                exito(f"Bienvenido, {nombre} [{self.gestor_usuarios.rol_actual}]")
            else:
                rprint("[bold red]Usuario o contraseña incorrectos.[/bold red]")

        elif sub == "logout":
            self.gestor_usuarios.logout()
            exito("Sesion cerrada.")

        elif sub == "whoami":
            self.gestor_usuarios.whoami()

        elif sub == "users":
            if len(parts) < 2:
                rprint(
                    "[yellow]Subcomandos: users list | users add <nombre> <pass> <rol> | "
                    "users delete <nombre> | users passwd <nombre> <nueva_pass>[/yellow]"
                )
                return
            accion = parts[1].lower()

            if accion == "list":
                self.gestor_usuarios.listar_usuarios()

            elif accion == "add":
                if len(parts) < 5:
                    rprint("[yellow]Uso: users add <nombre> <contraseña> <rol>[/yellow]")
                    rprint("[dim]Roles disponibles: admin, developer, viewer[/dim]")
                    return
                nombre, pwd, rol = parts[2], parts[3], parts[4].lower()
                if self.gestor_usuarios.agregar_usuario(nombre, pwd, rol):
                    exito(f"Usuario '{nombre}' creado con rol '{rol}'.")

            elif accion == "delete":
                if len(parts) < 3:
                    rprint("[yellow]Uso: users delete <nombre>[/yellow]")
                    return
                nombre = parts[2]
                try:
                    conf = input(f"Eliminar usuario '{nombre}'? (s/n): ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    conf = "n"
                if conf == "s" and self.gestor_usuarios.eliminar_usuario(nombre):
                    exito(f"Usuario '{nombre}' eliminado.")

            elif accion == "passwd":
                if len(parts) < 4:
                    rprint("[yellow]Uso: users passwd <nombre> <nueva_contraseña>[/yellow]")
                    return
                nombre, nueva = parts[2], parts[3]
                if self.gestor_usuarios.cambiar_password(nombre, nueva):
                    exito(f"Contraseña de '{nombre}' actualizada.")

            else:
                rprint(f"[red]Subcomando desconocido: '{accion}'. Usa: list, add, delete, passwd[/red]")

    def _handle_diff(self, command: str):
        """
        Compara las tablas de dos bases de datos.

        Formas de uso:
          diff                              — compara connector actual vs connector2 (si existe)
          diff <archivo.db>                 — compara actual vs otro SQLite
          diff <archivo.db> <archivo2.db>   — compara dos SQLite entre sí
          diff connect                      — muestra cómo configurar un segundo conector
        """
        if not self.connector or not self.connector.is_connected:
            rprint("[red]Primero conéctate a una base de datos con 'connect'.[/red]")
            return

        parts = command.strip().split()
        args  = parts[1:]  # todo después de "diff"

        # ── sin argumentos: usar connector2 si existe ─────────────────────────
        if not args:
            if self.connector2 and self.connector2.is_connected:
                comparar_bds(self.connector, self.connector2)
            else:
                rprint(
                    "[yellow]Uso del comando diff:[/yellow]\n\n"
                    "  [cyan]diff <archivo.db>[/cyan]\n"
                    "    Compara la BD actual con otro archivo SQLite.\n"
                    "    Ej: [white]diff otra_bd.db[/white]\n\n"
                    "  [cyan]diff <archivo1.db> <archivo2.db>[/cyan]\n"
                    "    Compara dos archivos SQLite entre sí.\n"
                    "    Ej: [white]diff produccion.db staging.db[/white]\n\n"
                    "  [cyan]connect2 sqlite <archivo.db>[/cyan]\n"
                    "    Conecta un segundo conector y luego escribe [white]diff[/white] para comparar."
                )
            return

        # ── helper: crear conector SQLite rápido ─────────────────────────────
        def _sqlite(path: str):
            from connectors.sqlite_connector import SQLiteConnector
            c = SQLiteConnector()
            c.connect(db_path=path)
            return c

        try:
            if len(args) == 1:
                # diff <archivo2.db>  →  actual vs archivo2
                c2 = _sqlite(args[0])
                comparar_bds(self.connector, c2)

            elif len(args) == 2:
                # diff <archivo1.db> <archivo2.db>  →  ambos SQLite
                c1 = _sqlite(args[0])
                c2 = _sqlite(args[1])
                comparar_bds(c1, c2)

            else:
                rprint("[red]Demasiados argumentos. Usa: diff [archivo1.db] [archivo2.db][/red]")

        except Exception as e:
            rprint(f"[red]Error al comparar: {e}[/red]")

    def _connect2(self, command: str):
        """Conecta un segundo conector SQLite para usar con 'diff'."""
        parts = command.split()
        if len(parts) < 3 or parts[1].lower() != "sqlite":
            rprint("[yellow]Uso: connect2 sqlite <archivo.db>[/yellow]")
            return
        db_path = parts[2]
        try:
            from connectors.sqlite_connector import SQLiteConnector
            self.connector2 = SQLiteConnector()
            self.connector2.connect(db_path=db_path)
            exito(f"Segundo conector listo: SQLite '{db_path}'")
        except Exception as e:
            rprint(f"[red]Error: {e}[/red]")
            self.connector2 = None

    # ── Control por voz (NexusVoice) ───────────────────────────────────────────

    def _get_voz(self):
        """Inicializa el asistente de voz la primera vez que se usa."""
        if self.voz is None:
            from features.asistente_voz import AsistenteVoz
            self.voz = AsistenteVoz()
        return self.voz

    def _voz_no_disponible(self, voz):
        """Muestra ayuda si las dependencias de voz no están instaladas."""
        ux_error("El control por voz no está disponible.")
        rprint(f"[dim]Detalle: {voz.error_init or 'dependencias ausentes'}[/dim]")
        rprint("[yellow]Instala las dependencias con:[/yellow]")
        rprint("  [white]pip install SpeechRecognition pyttsx3 pyaudio[/white]")

    def _procesar_voz(self, texto: str):
        """Traduce el texto reconocido a un comando y lo ejecuta, narrando el
        resultado en voz alta. Reutiliza ai_helper + el executor existentes."""
        voz = self._get_voz()
        cmd = expandir_abreviacion(texto).strip()
        low = cmd.lower()

        # Palabras clave que indican que ya es un comando directo (no lenguaje natural)
        directos = (
            "select", "insert", "update", "delete", "create", "drop", "show",
            "connect", "status", "disconnect", "find", "get ", "set ", "keys",
            "del ", "import", "export", "migrate", "panel", "help", "diff",
        )
        es_directo = any(low.startswith(k) for k in directos)

        if not es_directo:
            sql, fuente = generar_sql(cmd, self.connector, self.mode)
            if not sql:
                rprint("[yellow]💬 No reconocí ese comando por voz.[/yellow]")
                voz.hablar("No reconocí ese comando. ¿Puedes repetirlo?")
                return
            etiqueta = "🧠 IA" if fuente == "ia" else "🔤 patrón"
            rprint(f"[bold cyan]{etiqueta} → SQL generado:[/bold cyan] [white]{sql}[/white]")
            cmd = sql

        # Ejecutar y narrar el resultado
        prev = self.last_results
        try:
            self.execute(cmd)
        except Exception as e:
            rprint(f"[bold red]ERROR:[/bold red] {e}")
            voz.hablar("Ocurrió un error al ejecutar el comando.")
            return

        if self.last_results is not None and self.last_results is not prev:
            voz.hablar(resumir_resultado(self.last_results))
        else:
            voz.hablar("Listo.")

    def _handle_voice_once(self):
        """Captura un único comando por voz, lo ejecuta y vuelve al modo texto."""
        voz = self._get_voz()
        if not voz.disponible:
            self._voz_no_disponible(voz)
            return

        rprint("[bold magenta]🎙️  Escuchando... (habla ahora)[/bold magenta]")
        texto, err = voz.escuchar()
        if err:
            advertencia(err)
            return
        rprint(f"[bold green]👤 Escuché:[/bold green] [white]\"{texto}\"[/white]")
        self._procesar_voz(texto)

    def _handle_voice_test(self, command: str):
        """Simula el pipeline de voz SIN micrófono (respaldo para la demo).
        Uso: voice test <frase en español>"""
        # Quitar el prefijo 'voz test' / 'voice test'
        resto = command.strip()
        for pref in ("voice test", "voz test"):
            if resto.lower().startswith(pref):
                resto = resto[len(pref):].strip().strip('"').strip("'")
                break
        if not resto:
            rprint("[yellow]Uso: voice test <frase>[/yellow] — ej: voice test muestra usuarios")
            return
        rprint(f"[bold green]👤 (simulado):[/bold green] [white]\"{resto}\"[/white]")
        self._procesar_voz(resto)

    def _handle_voice_engine(self, command: str):
        """Cambia o muestra el motor de transcripción de voz.
        Uso: voice engine [auto|google|vosk]"""
        voz = self._get_voz()
        parts = command.strip().split()
        if len(parts) < 3:
            estado_vosk = "disponible" if voz.vosk_disponible() else "no instalado"
            rprint(
                f"[cyan]Motor de voz actual:[/cyan] [white]{voz.motor}[/white]\n"
                f"[dim]Offline (Vosk): {estado_vosk}[/dim]\n"
                "[yellow]Uso: voice engine auto|google|vosk[/yellow]\n"
                "  [white]auto[/white]   = Google online, con respaldo offline si no hay internet\n"
                "  [white]google[/white] = solo online (mejor precisión)\n"
                "  [white]vosk[/white]   = solo offline (sin internet)"
            )
            return
        motor = parts[2].lower()
        if motor in ("vosk", "auto") and not voz.vosk_disponible():
            advertencia("El modelo de voz offline (Vosk) no está instalado.")
            rprint("[dim]Instálalo con: pip install vosk  y descarga un modelo en español.[/dim]")
        if voz.set_motor(motor):
            exito(f"Motor de voz cambiado a '{motor}'.")
        else:
            rprint("[red]Motor no válido. Usa: auto, google o vosk.[/red]")

    def _handle_voice_loop(self):
        """Modo voz continuo: escucha, ejecuta y responde hasta oír 'salir'."""
        voz = self._get_voz()
        if not voz.disponible:
            self._voz_no_disponible(voz)
            return

        banner = Text()
        banner.append("🎙️  MODO VOZ ACTIVADO\n", style="bold magenta")
        banner.append("Habla un comando en español tras el aviso.\n", style="white")
        banner.append("Di ", style="dim")
        banner.append("'salir'", style="bold yellow")
        banner.append(" o ", style="dim")
        banner.append("Ctrl+C", style="bold yellow")
        banner.append(" para volver al modo texto.", style="dim")
        self.console.print(Panel(banner, border_style="magenta", expand=False))
        voz.hablar("Modo voz activado. Te escucho.")

        fallos = 0
        while True:
            try:
                rprint("\n[bold magenta]🎙️  Escuchando...[/bold magenta]")
                texto, err = voz.escuchar()

                if err:
                    advertencia(err)
                    fallos += 1
                    if fallos >= 4:
                        rprint("[yellow]Demasiados intentos fallidos. Saliendo del modo voz.[/yellow]")
                        voz.hablar("Saliendo del modo voz.")
                        break
                    continue

                fallos = 0
                rprint(f"[bold green]👤 Escuché:[/bold green] [white]\"{texto}\"[/white]")

                if es_palabra_salir(texto):
                    voz.hablar("Saliendo del modo voz. Hasta luego.")
                    rprint("[bold magenta]🎙️  Modo voz desactivado.[/bold magenta]")
                    break

                self._procesar_voz(texto)

            except KeyboardInterrupt:
                rprint("\n[bold magenta]🎙️  Modo voz desactivado.[/bold magenta]")
                break

    # ==================== COMANDOS BÁSICOS ====================

    def _exit(self):
        """Salir de la aplicación"""
        if self.connector and self.connector.is_connected:
            self._disconnect()
        self.programador.detener()
        rprint("\n[bold cyan]👋 Hasta luego — Nexus-DB[/bold cyan]")
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
        help_text.append("  migrate <origen> <destino> <salida> [--sim] - Migrar base de datos por ETL\n")
        help_text.append("  validate backup <ruta> <motor> <db_name>    - Validar integridad de backup en Docker\n")

        help_text.append("\n🎙️  CONTROL POR VOZ (NexusVoice):\n", style="bold magenta")
        help_text.append("  voice                                       - Modo voz continuo (habla tus comandos)\n")
        help_text.append("  voice once                                  - Captura un solo comando por voz\n")
        help_text.append("  voice test <frase>                          - Prueba el pipeline de voz sin micrófono\n")
        help_text.append("  voice engine auto|google|vosk               - Motor de voz (vosk = offline, sin internet)\n")

        help_text.append("\nNEXUS-DB EXTENSIONS:\n", style="bold green")
        help_text.append('  ai "<texto>"                                - Convierte español a SQL con IA (Claude) y lo ejecuta\n')
        help_text.append("  panel                                       - Panel de consultas activas / lentas\n")
        help_text.append("  schedule add <cmd> at HH:MM                 - Programar tarea diaria\n")
        help_text.append("  schedule add <cmd> every N hours            - Programar tarea periódica\n")
        help_text.append("  schedule list                               - Listar tareas programadas\n")
        help_text.append("  schedule cancel <id>                        - Cancelar tarea\n")
        help_text.append("  diff [archivo2.db]                          - Comparar tablas: actual vs otro SQLite\n")
        help_text.append("  diff <archivo1.db> <archivo2.db>            - Comparar dos archivos SQLite\n")
        help_text.append("  connect2 sqlite <archivo.db>                - Conectar 2do conector para diff\n")

        help_text.append("\nUSUARIOS:\n", style="bold magenta")
        help_text.append("  login <usuario> <contraseña>                - Iniciar sesión\n")
        help_text.append("  logout                                      - Cerrar sesión\n")
        help_text.append("  whoami                                      - Ver usuario y rol actuales\n")
        help_text.append("  users list                                  - Listar usuarios (admin)\n")
        help_text.append("  users add <nombre> <pass> <rol>             - Crear usuario (admin)\n")
        help_text.append("  users delete <nombre>                       - Eliminar usuario (admin)\n")
        help_text.append("  users passwd <nombre> <nueva_pass>          - Cambiar contraseña\n")
        help_text.append("  cls / clear                                 - Limpiar pantalla\n")

        help_text.append("\n  help                                        - Muestra esta ayuda\n")
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
                self.formatter.print_table(data['columns'], data['rows'], paginate=True)
                rprint(f"\n[bold cyan]INFO: Total:[/bold cyan] [white]{len(data['rows'])} fila(s)[/white]")
            elif data and 'affected_rows' in data:
                rprint(f"[bold green]OK: Éxito:[/bold green] [white]{data['affected_rows']} fila(s) afectada(s)[/white]")
            else:
                rprint("[bold yellow]INFO: Consulta ejecutada sin resultados.[/bold yellow]")
        else:
            rprint(f"[bold red]ERROR SQL:[/bold red] [white]{error}[/white]")

    def _export(self, command: str):
        """Exporta los últimos resultados a un archivo CSV, JSON o TXT"""
        parts = command.split()
        if len(parts) < 2:
            rprint("[bold red]ERROR:[/bold red] Debes especificar un nombre de archivo. [yellow]Ej: export resultados.csv[/yellow]")
            return

        if not self.last_results:
            rprint("[bold yellow]INFO: No hay resultados para exportar.[/bold yellow] [white]Primero realiza un SELECT.[/white]")
            return

        filename = parts[1]
        try:
            if filename.endswith(".json"):
                import json
                rows = self.last_results['rows']
                cols = self.last_results['columns']
                data_list = [dict(zip(cols, row)) for row in rows]
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data_list, f, indent=4, default=str)
            elif filename.endswith(".txt") or filename.endswith(".md"):
                from rich.console import Console
                with open(filename, 'w', encoding='utf-8') as f:
                    f_console = Console(file=f, force_terminal=False)
                    self.formatter.print_table(self.last_results['columns'], self.last_results['rows'], custom_console=f_console)
            else:
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