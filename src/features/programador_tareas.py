"""
Programador de tareas: ejecuta comandos de Nexus-DB de forma automática.
Soporta ejecución en hora fija (at HH:MM) y periódica (every N hours).
Las tareas se persisten en tareas.json y se ejecutan en hilo de fondo.
"""

import json
import os
import threading
import time
from datetime import datetime, timedelta

from rich.console import Console
from rich.table import Table

console = Console()

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAREAS_FILE = os.path.join(_BASE_DIR, "tareas.json")


class ProgramadorTareas:
    """Gestiona tareas programadas para el REPL de Nexus-DB."""

    def __init__(self, repl_execute_fn=None):
        self.repl_execute = repl_execute_fn
        self.tareas: list = []
        self._next_id: int = 1
        self._activo = False
        self._hilo: threading.Thread | None = None
        self._lock = threading.Lock()
        self._cargar()
        self._iniciar_hilo()

    # ── persistencia ──────────────────────────────────────────────────────────

    def _cargar(self):
        if os.path.exists(TAREAS_FILE):
            try:
                with open(TAREAS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.tareas = data.get("tareas", [])
                self._next_id = data.get("next_id", 1)
            except Exception:
                pass

    def _guardar(self):
        with self._lock:
            with open(TAREAS_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {"tareas": self.tareas, "next_id": self._next_id},
                    f, indent=2, ensure_ascii=False
                )

    # ── hilo de fondo ─────────────────────────────────────────────────────────

    def _iniciar_hilo(self):
        self._activo = True
        self._hilo = threading.Thread(target=self._loop, daemon=True, name="nexusdb-scheduler")
        self._hilo.start()

    def _loop(self):
        while self._activo:
            ahora = datetime.now()
            for tarea in list(self.tareas):
                if not tarea.get("activa", True):
                    continue
                proxima_str = tarea.get("proxima_ejecucion")
                if not proxima_str:
                    continue
                try:
                    proxima = datetime.fromisoformat(proxima_str)
                except ValueError:
                    continue
                if proxima <= ahora:
                    self._ejecutar(tarea, ahora)
            time.sleep(30)

    def _ejecutar(self, tarea: dict, ahora: datetime):
        comando = tarea["comando"]
        console.print(f"\n[bold yellow]⏰ [Scheduler] Ejecutando:[/bold yellow] [cyan]{comando}[/cyan]")
        if self.repl_execute:
            try:
                self.repl_execute(comando)
            except Exception as e:
                console.print(f"[red]Error en tarea programada: {e}[/red]")

        # Calcular próxima ejecución
        if tarea["tipo"] == "every":
            horas = tarea["intervalo_horas"]
            tarea["proxima_ejecucion"] = (ahora + timedelta(hours=horas)).isoformat()
        elif tarea["tipo"] == "at":
            h, m = tarea["hora"].split(":")
            proxima = ahora.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
            if proxima <= ahora:
                proxima += timedelta(days=1)
            tarea["proxima_ejecucion"] = proxima.isoformat()

        self._guardar()

    # ── API pública ───────────────────────────────────────────────────────────

    def agregar_at(self, comando: str, hora: str) -> int:
        """Programa un comando para ejecutarse a una hora fija cada día (HH:MM)."""
        try:
            h, m = hora.split(":")
            int(h); int(m)
        except ValueError:
            raise ValueError(f"Formato de hora inválido: '{hora}'. Usa HH:MM")

        ahora = datetime.now()
        proxima = ahora.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
        if proxima <= ahora:
            proxima += timedelta(days=1)

        tarea = {
            "id": self._next_id,
            "comando": comando,
            "tipo": "at",
            "hora": hora,
            "proxima_ejecucion": proxima.isoformat(),
            "activa": True,
            "creada": ahora.isoformat(),
        }
        self.tareas.append(tarea)
        self._next_id += 1
        self._guardar()
        return tarea["id"]

    def agregar_every(self, comando: str, horas: int) -> int:
        """Programa un comando para ejecutarse cada N horas."""
        if horas <= 0:
            raise ValueError("El intervalo debe ser mayor a 0 horas")

        ahora = datetime.now()
        proxima = ahora + timedelta(hours=horas)

        tarea = {
            "id": self._next_id,
            "comando": comando,
            "tipo": "every",
            "intervalo_horas": horas,
            "proxima_ejecucion": proxima.isoformat(),
            "activa": True,
            "creada": ahora.isoformat(),
        }
        self.tareas.append(tarea)
        self._next_id += 1
        self._guardar()
        return tarea["id"]

    def listar(self):
        """Muestra todas las tareas en una tabla Rich."""
        activas = [t for t in self.tareas if t.get("activa", True)]
        canceladas = [t for t in self.tareas if not t.get("activa", True)]

        if not self.tareas:
            console.print("[yellow]No hay tareas programadas.[/yellow]")
            return

        table = Table(title="📅 Tareas Programadas", border_style="blue", show_lines=True)
        table.add_column("#", style="cyan", width=4, justify="right")
        table.add_column("Comando", style="white", overflow="fold")
        table.add_column("Tipo", style="yellow")
        table.add_column("Próxima Ejecución", style="green")
        table.add_column("Estado", style="bold")

        for t in self.tareas:
            estado = "✅ Activa" if t.get("activa", True) else "🔴 Cancelada"
            if t["tipo"] == "at":
                tipo_str = f"diario a las {t['hora']}"
            else:
                tipo_str = f"cada {t['intervalo_horas']}h"

            proxima = t.get("proxima_ejecucion", "-")
            proxima = proxima[:16] if proxima and proxima != "-" else "-"
            table.add_row(str(t["id"]), t["comando"], tipo_str, proxima, estado)

        console.print(table)
        console.print(f"[dim]{len(activas)} activa(s), {len(canceladas)} cancelada(s)[/dim]")

    def cancelar(self, tarea_id: int) -> bool:
        """Desactiva una tarea por ID. Retorna True si se encontró."""
        for t in self.tareas:
            if t["id"] == tarea_id:
                t["activa"] = False
                self._guardar()
                return True
        return False

    def detener(self):
        """Detiene el hilo de fondo (para shutdown limpio)."""
        self._activo = False
