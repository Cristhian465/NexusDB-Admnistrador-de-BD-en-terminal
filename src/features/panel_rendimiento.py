"""
Panel de rendimiento: muestra consultas activas / procesos lentos del motor conectado.
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

# Queries por motor
_QUERY_POSTGRES = (
    "SELECT pid, LEFT(query, 70) AS query, "
    "COALESCE(EXTRACT(EPOCH FROM (now() - query_start))::int, 0) AS duracion_s, "
    "state, usename "
    "FROM pg_stat_activity "
    "WHERE state = 'active' AND query NOT ILIKE '%pg_stat_activity%' "
    "ORDER BY query_start ASC LIMIT 5"
)

_QUERY_MYSQL = (
    "SELECT id, user, command, time, LEFT(IFNULL(info,''), 70) "
    "FROM information_schema.processlist "
    "WHERE command != 'Sleep' ORDER BY time DESC LIMIT 5"
)


def mostrar_panel(connector) -> None:
    """Muestra el panel de rendimiento para el conector activo."""
    if not connector or not connector.is_connected:
        console.print("[bold red]❌ No hay conexión activa.[/bold red]")
        return

    db_type = connector.get_type().lower()

    if "postgres" in db_type:
        _mostrar_relacional(connector, _QUERY_POSTGRES,
                            ["#", "Consulta", "Tiempo (s)", "Estado", "Usuario"])

    elif "mysql" in db_type:
        _mostrar_relacional(connector, _QUERY_MYSQL,
                            ["#", "Usuario", "Comando", "Tiempo (s)", "Consulta"])

    elif "sqlite" in db_type:
        console.print(Panel(
            "[yellow]SQLite no soporta monitoreo de procesos activos.[/yellow]\n"
            "[dim]SQLite es un motor embebido sin servidor de procesos.[/dim]",
            title="[bold white]Panel de Rendimiento[/bold white]",
            border_style="yellow"
        ))

    elif "mongodb" in db_type:
        console.print(Panel(
            "[yellow]MongoDB no soporta monitoreo vía este panel.\n"
            "Usa db.currentOp() en mongosh para ver operaciones activas.[/yellow]",
            title="[bold white]Panel de Rendimiento[/bold white]",
            border_style="yellow"
        ))

    elif "redis" in db_type:
        console.print(Panel(
            "[yellow]Redis no soporta monitoreo de consultas vía este panel.\n"
            "Usa el comando INFO en redis-cli para estadísticas.[/yellow]",
            title="[bold white]Panel de Rendimiento[/bold white]",
            border_style="yellow"
        ))

    elif "cassandra" in db_type:
        console.print(Panel(
            "[yellow]Cassandra no soporta monitoreo de consultas vía este panel.[/yellow]",
            title="[bold white]Panel de Rendimiento[/bold white]",
            border_style="yellow"
        ))

    else:
        console.print(f"[red]Motor desconocido: {db_type}[/red]")


def _mostrar_relacional(connector, query: str, col_names: list) -> None:
    success, data, error = connector.execute_query(query)

    table = Table(
        title="⚡ Consultas Activas",
        border_style="blue",
        show_lines=True
    )
    for col in col_names:
        table.add_column(col, overflow="fold")

    if not success:
        console.print(f"[red]Error al consultar procesos: {error}[/red]")
        return

    rows = data.get("rows", []) if data else []
    if not rows:
        console.print("[green]✅ No hay consultas lentas activas.[/green]")
        return

    for i, row in enumerate(rows, 1):
        table.add_row(str(i), *[str(v)[:70] if v is not None else "NULL" for v in row[1:]])

    console.print(table)
    console.print(f"[dim]{len(rows)} proceso(s) mostrado(s)[/dim]")
