#!/usr/bin/env python3
"""
Administrador de BD por Consola
Aplicación CLI para administración de bases de datos relacionales
"""

import sys
from cli.repl import REPL
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

def main():
    """Punto de entrada principal"""
    import os
    if os.name == 'nt':
        import ctypes
        import sys
        
        # Set Window Title
        ctypes.windll.kernel32.SetConsoleTitleW("Database Administrator CLI")
        
        # Set Window Icon
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            hinst = ctypes.windll.kernel32.GetModuleHandleW(None)
            exe_path = sys.executable
            # Extract the first icon from the executable (0)
            hicon = ctypes.windll.shell32.ExtractIconW(hinst, exe_path, 0)
            if hicon:
                # WM_SETICON = 0x0080
                ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon) # ICON_SMALL
                ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon) # ICON_BIG
                
    console = Console()
    try:
        logo = r"""
  ____  ____     ____ _     ___ 
 |  _ \| __ )   / ___| |   |_ _|
 | | | |  _ \  | |   | |    | | 
 | |_| | |_) | | |___| |___ | | 
 |____/|____/   \____|_____|___|
        """
        console.print(Panel(
            Text(logo, style="bold cyan"),
            title="[bold white]Database Administrator CLI[/bold white]",
            subtitle="[yellow]v1.1 - Presentation Ready[/yellow]",
            expand=False
        ))

        menu_text = Text()
        menu_text.append("\nSeleccione el entorno de base de datos a gestionar:\n\n", style="bold white")
        menu_text.append("  [1] ", style="bold green")
        menu_text.append("Relacional ", style="bold cyan")
        menu_text.append("(SQLite, PostgreSQL, MySQL)\n")
        menu_text.append("  [2] ", style="bold green")
        menu_text.append("NoSQL      ", style="bold magenta")
        menu_text.append("(MongoDB, Redis, Cassandra)\n")
        
        console.print(Panel(menu_text, title="[bold white]MODO DE OPERACIÓN[/bold white]", border_style="blue", expand=False))
        
        while True:
            console.print("[bold yellow]Opción [1/2]: [/bold yellow]", end="")
            choice = input().strip()
            if choice == '1':
                mode = 'rel'
                console.print("\n[bold green]Iniciando modo Relacional... Escribe 'help' para comandos.[/bold green]\n")
                break
            elif choice == '2':
                mode = 'nosql'
                console.print("\n[bold magenta]Iniciando modo NoSQL... Escribe 'help' para comandos.[/bold magenta]\n")
                break
            else:
                console.print("[bold red]❌ Por favor, seleccione 1 o 2.[/bold red]")
                
        repl = REPL(mode=mode)
        repl.run()
    except KeyboardInterrupt:
        print("\n\n¡Hasta luego!")
        sys.exit(0)
    except Exception as e:
        print(f"\nError inesperado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
