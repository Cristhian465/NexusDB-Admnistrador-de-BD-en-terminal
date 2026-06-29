"""
Gestor de Consultas Favoritas (Bookmarks)
"""
import os
import json
from rich import print as rprint

BOOKMARKS_FILE = os.path.expanduser('~/.nexusdb_bookmarks.json')

class BookmarkManager:
    def __init__(self):
        self.bookmarks = self._load()

    def _load(self):
        if not os.path.exists(BOOKMARKS_FILE):
            return {}
        try:
            with open(BOOKMARKS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self):
        try:
            with open(BOOKMARKS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.bookmarks, f, indent=4)
            return True
        except Exception as e:
            rprint(f"[red]Error al guardar bookmarks: {e}[/red]")
            return False

    def get(self, alias):
        return self.bookmarks.get(alias)

    def add(self, alias, sql):
        self.bookmarks[alias] = sql
        return self._save()

    def delete(self, alias):
        if alias in self.bookmarks:
            del self.bookmarks[alias]
            return self._save()
        return False

    def list_all(self):
        if not self.bookmarks:
            rprint("[yellow]No tienes consultas favoritas guardadas.[/yellow]")
            return
        
        from rich.table import Table
        from rich.console import Console
        
        table = Table(title="Consultas Favoritas (Bookmarks)", border_style="cyan")
        table.add_column("Alias", style="bold green")
        table.add_column("Consulta SQL", style="white", overflow="fold")
        
        for alias, sql in self.bookmarks.items():
            table.add_row(alias, sql)
            
        Console().print(table)
