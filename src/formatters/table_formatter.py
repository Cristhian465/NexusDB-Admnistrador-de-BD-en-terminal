"""
Formateador de resultados en formato tabla usando Rich
"""

from rich.table import Table
from rich.console import Console


class TableFormatter:
    """Formatea los resultados de consultas usando la librería Rich"""

    def __init__(self):
        self.console = Console()

    def print_table(self, columns: list, rows: list, custom_console=None, paginate=False):
        """
        Imprime una tabla elegante con los resultados
        
        Args:
            columns: Lista de nombres de columnas
            rows: Lista de filas (cada fila es una lista de valores)
            custom_console: Consola opcional para exportación.
            paginate: Si es True, pagina manualmente los resultados de 50 en 50.
        """
        if not columns:
            return
            
        c = custom_console or self.console

        def _print_chunk(chunk_rows):
            table = Table(
                show_header=True, 
                header_style="bold magenta",
                border_style="cyan",
                row_styles=["none", "dim"],
                box=None
            )
            for col in columns:
                table.add_column(str(col))
            for row in chunk_rows:
                table.add_row(*[str(val) for val in row])
            c.print(table)

        if paginate and len(rows) > 50:
            for i in range(0, len(rows), 50):
                chunk = rows[i:i+50]
                _print_chunk(chunk)
                if i + 50 < len(rows):
                    try:
                        resp = input(f"Mostrando {i+50} de {len(rows)}. Presiona Enter para más, 'q' para salir... ").strip().lower()
                        if resp == 'q':
                            break
                    except (KeyboardInterrupt, EOFError):
                        break
        else:
            _print_chunk(rows)
