"""
Gestión de usuarios y auditoría de Nexus-DB.
Roles: admin (todo), developer (CRUD + panel + AI), viewer (solo lectura).
Persiste en usuarios.json y registra acciones en audit.log.
"""

import hashlib
import json
import os
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USUARIOS_FILE = os.path.join(_BASE_DIR, "usuarios.json")
AUDIT_FILE = os.path.join(_BASE_DIR, "audit.log")

# Comandos permitidos por rol (prefijos en minúsculas)
PERMISOS: dict[str, list[str]] = {
    "admin": ["*"],
    "developer": [
        "connect", "disconnect", "status", "select", "insert", "update",
        "export", "export_sql", "export_db", "import", "import_db",
        "panel", "ai", "schedule", "diff", "show", "find", "set", "get",
        "del", "keys", "migrate",
    ],
    "viewer": [
        "connect", "disconnect", "status", "select",
        "export", "export_sql", "show", "find", "get", "keys",
    ],
}


class GestorUsuarios:
    """Maneja autenticación, roles y auditoría."""

    def __init__(self):
        self.usuario_actual: str | None = None
        self.rol_actual: str | None = None
        self._inicializar()

    # ── bootstrap ──────────────────────────────────────────────────────────────

    def _inicializar(self):
        """Crea usuarios.json con el usuario admin si no existe."""
        if not os.path.exists(USUARIOS_FILE):
            data = {
                "usuarios": [
                    {
                        "nombre": "admin",
                        "password_hash": self._hash("1234"),
                        "rol": "admin",
                        "creado": datetime.now().isoformat(),
                    }
                ]
            }
            self._guardar(data)

    # ── persistencia ──────────────────────────────────────────────────────────

    def _hash(self, password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def _cargar(self) -> dict:
        with open(USUARIOS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def _guardar(self, data: dict):
        with open(USUARIOS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _auditar(self, accion: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user = self.usuario_actual or "anon"
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {user} | {accion}\n")

    # ── autenticación ─────────────────────────────────────────────────────────

    def login(self, nombre: str, password: str) -> bool:
        data = self._cargar()
        for u in data["usuarios"]:
            if u["nombre"] == nombre and u["password_hash"] == self._hash(password):
                self.usuario_actual = nombre
                self.rol_actual = u["rol"]
                self._auditar("LOGIN exitoso")
                return True
        self._auditar(f"LOGIN fallido para '{nombre}'")
        return False

    def logout(self):
        self._auditar("LOGOUT")
        self.usuario_actual = None
        self.rol_actual = None

    def whoami(self):
        if self.usuario_actual:
            panel = Panel(
                f"[bold cyan]Usuario:[/bold cyan] {self.usuario_actual}\n"
                f"[bold cyan]Rol:[/bold cyan]     {self.rol_actual}",
                title="[bold white]Sesión Activa[/bold white]",
                border_style="green",
                expand=False,
            )
            console.print(panel)
        else:
            console.print("[yellow]No hay sesión activa. Usa 'login <usuario> <contraseña>'.[/yellow]")

    # ── permisos ──────────────────────────────────────────────────────────────

    def tiene_permiso(self, comando: str) -> bool:
        """Verifica si el usuario actual puede ejecutar el comando."""
        if not self.usuario_actual:
            return True  # Modo sin autenticación: todo permitido
        perms = PERMISOS.get(self.rol_actual, [])
        if "*" in perms:
            return True
        cmd_base = comando.strip().lower().split()[0] if comando.strip() else ""
        return any(cmd_base.startswith(p) for p in perms)

    # ── administración ────────────────────────────────────────────────────────

    def listar_usuarios(self):
        if self.rol_actual != "admin":
            console.print("[bold red]Solo el rol admin puede listar usuarios.[/bold red]")
            return
        data = self._cargar()
        table = Table(title="Usuarios del Sistema", border_style="blue")
        table.add_column("Usuario", style="cyan")
        table.add_column("Rol", style="yellow")
        table.add_column("Creado", style="white")
        for u in data["usuarios"]:
            table.add_row(u["nombre"], u["rol"], u.get("creado", "-")[:10])
        console.print(table)

    def agregar_usuario(self, nombre: str, password: str, rol: str) -> bool:
        """Crea un usuario nuevo. Solo admin puede hacerlo."""
        if self.rol_actual != "admin":
            console.print("[bold red]Solo el rol admin puede crear usuarios.[/bold red]")
            return False

        roles_validos = list(PERMISOS.keys())
        if rol not in roles_validos:
            console.print(f"[red]Rol invalido. Opciones: {', '.join(roles_validos)}[/red]")
            return False

        data = self._cargar()
        if any(u["nombre"] == nombre for u in data["usuarios"]):
            console.print(f"[yellow]El usuario '{nombre}' ya existe.[/yellow]")
            return False

        data["usuarios"].append({
            "nombre": nombre,
            "password_hash": self._hash(password),
            "rol": rol,
            "creado": datetime.now().isoformat(),
        })
        self._guardar(data)
        self._auditar(f"USUARIO CREADO: {nombre} [{rol}]")
        return True

    def cambiar_password(self, nombre: str, nueva_pass: str) -> bool:
        """Cambia la contraseña de un usuario. Admin puede cambiar cualquiera; el usuario solo la propia."""
        if self.rol_actual != "admin" and self.usuario_actual != nombre:
            console.print("[red]No tienes permiso para cambiar esa contraseña.[/red]")
            return False
        data = self._cargar()
        for u in data["usuarios"]:
            if u["nombre"] == nombre:
                u["password_hash"] = self._hash(nueva_pass)
                self._guardar(data)
                self._auditar(f"PASSWORD CAMBIADO: {nombre}")
                return True
        console.print(f"[red]Usuario '{nombre}' no encontrado.[/red]")
        return False

    def eliminar_usuario(self, nombre: str) -> bool:
        """Elimina un usuario (solo admin, no puede eliminarse a sí mismo)."""
        if self.rol_actual != "admin":
            console.print("[red]Solo el rol admin puede eliminar usuarios.[/red]")
            return False
        if nombre == self.usuario_actual:
            console.print("[yellow]No puedes eliminarte a ti mismo.[/yellow]")
            return False
        data = self._cargar()
        antes = len(data["usuarios"])
        data["usuarios"] = [u for u in data["usuarios"] if u["nombre"] != nombre]
        if len(data["usuarios"]) == antes:
            console.print(f"[red]Usuario '{nombre}' no encontrado.[/red]")
            return False
        self._guardar(data)
        self._auditar(f"USUARIO ELIMINADO: {nombre}")
        return True

    def registrar_comando(self, comando: str):
        """Audita un comando ejecutado."""
        self._auditar(f"CMD: {comando}")
