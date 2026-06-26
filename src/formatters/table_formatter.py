"""
Formateador de resultados en formato tabla usando Rich
"""

from rich.table import Table
from rich.console import Console


class TableFormatter:
    """Formatea los resultados de consultas usando la librería Rich"""

    def __init__(self):
        self.console = Console()

    def print_table(self, columns: list, rows: list):
        """
        Imprime una tabla elegante con los resultados
        
        Args:
            columns: Lista de nombres de columnas
            rows: Lista de filas (cada fila es una lista de valores)
        """
        if not columns:
            return

        table = Table(
            show_header=True, 
            header_style="bold magenta",
            border_style="cyan",
            row_styles=["none", "dim"],
            box=None # O puedes usar box.ROUNDED para bordes redondeados
        )

        for col in columns:
            table.add_column(str(col))

        for row in rows:
            # Convertir todos los valores a string para rich
            table.add_row(*[str(val) for val in row])

        self.console.print(table)
