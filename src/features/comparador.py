"""
Comparador de bases de datos y guardia de seguridad para comandos peligrosos.
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

# Patrones que requieren confirmación
_PELIGROS = [
    ("drop",            "DROP eliminará la tabla permanentemente"),
    ("truncate",        "TRUNCATE borrará TODOS los datos de la tabla"),
    ("alter",           "ALTER modificará la estructura de la tabla"),
]


def revisar_seguridad(comando: str) -> bool:
    """
    Revisa si el comando es peligroso y pide confirmación al usuario.
    Retorna True si se debe continuar, False si se canceló.
    """
    cmd = comando.lower().strip()

    alertas = []

    for patron, descripcion in _PELIGROS:
        if cmd.startswith(patron):
            alertas.append(descripcion)

    # DELETE o UPDATE sin WHERE
    if cmd.startswith("delete") and "where" not in cmd:
        alertas.append("DELETE sin WHERE eliminará TODOS los registros de la tabla")
    if cmd.startswith("update") and "where" not in cmd:
        alertas.append("UPDATE sin WHERE actualizará TODOS los registros")

    if not alertas:
        return True

    # Mostrar advertencias
    console.print()
    for alerta in alertas:
        console.print(f"[bold red][!] ADVERTENCIA:[/bold red] {alerta}")

    try:
        resp = input("¿Continuar de todas formas? (s/n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        resp = "n"

    if resp != "s":
        console.print("[bold yellow]Operacion cancelada.[/bold yellow]")
        return False

    return True


def comparar_bds(connector1, connector2) -> None:
    """
    Compara las tablas de dos conectores activos y muestra las diferencias
    en una tabla Rich con columnas: Tabla, En BD1, En BD2.
    """
    if not connector1 or not connector1.is_connected:
        console.print("[red]❌ El primer conector no está activo.[/red]")
        return
    if not connector2 or not connector2.is_connected:
        console.print("[red]❌ El segundo conector no está activo.[/red]")
        return

    s1, tablas1, e1 = connector1.get_tables()
    s2, tablas2, e2 = connector2.get_tables()

    if not s1:
        console.print(f"[red]Error al leer BD1: {e1}[/red]")
        return
    if not s2:
        console.print(f"[red]Error al leer BD2: {e2}[/red]")
        return

    set1 = set(tablas1 or [])
    set2 = set(tablas2 or [])
    todas = sorted(set1 | set2)

    solo_en_1 = set1 - set2
    solo_en_2 = set2 - set1
    en_ambas  = set1 & set2

    table = Table(
        title=(
            f"🔍 Comparación: [{connector1.get_type()} {connector1.get_info()}]"
            f"  vs  [{connector2.get_type()} {connector2.get_info()}]"
        ),
        border_style="blue",
        show_lines=True,
    )
    table.add_column("Tabla / Colección", style="white")
    table.add_column(f"BD1 ({connector1.get_type()})", justify="center", style="cyan")
    table.add_column(f"BD2 ({connector2.get_type()})", justify="center", style="magenta")
    table.add_column("Diferencia", style="bold")

    for t in todas:
        en_1 = "✅" if t in set1 else "—"
        en_2 = "✅" if t in set2 else "—"
        if t in en_ambas:
            diff = "[green]Igual[/green]"
        elif t in solo_en_1:
            diff = "[yellow]Solo en BD1[/yellow]"
        else:
            diff = "[yellow]Solo en BD2[/yellow]"
        table.add_row(t, en_1, en_2, diff)

    console.print(table)

    # Resumen
    console.print(
        f"[dim]Tablas comunes: {len(en_ambas)} | "
        f"Solo en BD1: {len(solo_en_1)} | "
        f"Solo en BD2: {len(solo_en_2)}[/dim]"
    )
