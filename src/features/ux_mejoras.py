"""
Mejoras de experiencia de usuario: helpers de color, emojis por motor,
sugerencias contextuales y completions extras para el REPL.
"""

from rich.console import Console
from rich.panel import Panel

console = Console()

# ── Emojis por motor ──────────────────────────────────────────────────────────

_EMOJIS: dict[str, str] = {
    "sqlite":    "📂",
    "postgres":  "🐘",
    "mysql":     "🐬",
    "mongodb":   "🍃",
    "redis":     "🔴",
    "cassandra": "🪐",
}


def emoji_motor(db_type: str) -> str:
    for key, emoji in _EMOJIS.items():
        if key in db_type.lower():
            return emoji
    return "🗄️"


# ── Mensajes estilizados ───────────────────────────────────────────────────────

def exito(msg: str):
    console.print(f"[bold green]✅ {msg}[/bold green]")

def error(msg: str):
    console.print(f"[bold red]❌ {msg}[/bold red]")

def advertencia(msg: str):
    console.print(f"[bold yellow]⚠️  {msg}[/bold yellow]")

def info(msg: str):
    console.print(f"[bold cyan]💡 {msg}[/bold cyan]")

def peligro(msg: str):
    console.print(f"[bold red on dark_red]🚨 {msg}[/bold red on dark_red]")

def conexion(msg: str):
    console.print(f"[bold blue]🔌 {msg}[/bold blue]")

def datos(msg: str):
    console.print(f"[bold magenta]📊 {msg}[/bold magenta]")

def horario(msg: str):
    console.print(f"[bold yellow]⏰ {msg}[/bold yellow]")


# ── Sugerencias contextuales ──────────────────────────────────────────────────

_SUGERENCIAS: dict[str, str] = {
    "connect": (
        "Ejemplos de conexión:\n"
        "  connect sqlite mi_db.db\n"
        "  connect postgres mi_bd admin 1234\n"
        "  connect mysql mi_bd root 1234\n"
        "  connect mongodb mi_bd localhost 27017"
    ),
    "select": (
        "Sintaxis: select * from <tabla> [where <condicion>]\n"
        "Ej: select * from usuarios where activo = 1"
    ),
    "delete": (
        "⚠️  Siempre incluye WHERE para evitar borrar toda la tabla.\n"
        "Ej: delete from usuarios where id = 5"
    ),
    "ai": (
        "Ejemplos de lenguaje natural:\n"
        '  ai "muestra usuarios"\n'
        '  ai "cuantos clientes hay"\n'
        '  ai "muestra los 5 productos mas caros"\n'
        '  ai "inserta usuario nombre Ana edad 30"'
    ),
    "schedule": (
        "Comandos disponibles:\n"
        "  schedule add <cmd> at HH:MM\n"
        "  schedule add <cmd> every <N> hours\n"
        "  schedule list\n"
        "  schedule cancel <id>"
    ),
    "migrate": (
        "Sintaxis: migrate <archivo_origen> <motor_destino> <salida.sql> [--sim]\n"
        "Ej: migrate test.db postgres dump_pg.sql"
    ),
    "diff": (
        "Compara tablas entre dos conexiones guardadas.\n"
        "Debes tener dos conectores activos (con --extra-connector).\n"
        "Ej: diff sqlite:a.db postgres:mi_bd"
    ),
}


def mostrar_sugerencia(cmd: str):
    """Muestra una sugerencia contextual si el comando tiene una definida."""
    base = cmd.strip().lower().split()[0] if cmd.strip() else ""
    if base in _SUGERENCIAS:
        console.print(Panel(
            _SUGERENCIAS[base],
            title=f"[bold white]💡 Ayuda: {base}[/bold white]",
            border_style="dim",
            expand=False,
        ))


# ── Completions adicionales para el autocompletado del REPL ──────────────────

COMPLETIONS_EXTRA = [
    "voice",
    "voice once",
    "voice test ",
    "ai ",
    "panel",
    "schedule add ",
    "schedule list",
    "schedule cancel ",
    "login ",
    "logout",
    "whoami",
    "users list",
    "diff ",
]

# Expansiones de abreviaciones (prefijo -> expansión)
ABREVIACIONES: dict[str, str] = {
    "sel":      "select * from ",
    "conn":     "connect ",
    "ex ":      "export ",
    "exs":      "export_sql ",
    "exdb":     "export_db ",
    "sched":    "schedule ",
    "disc":     "disconnect",
    "stat":     "status",
    "wh":       "whoami",
}


def expandir_abreviacion(texto: str) -> str:
    """Si el texto es una abreviación conocida, devuelve su expansión; si no, retorna el mismo texto."""
    lower = texto.lower().strip()
    return ABREVIACIONES.get(lower, texto)
