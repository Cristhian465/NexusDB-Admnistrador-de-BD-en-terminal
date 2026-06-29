"""
Conector para SQLite
"""

import sqlite3
from typing import Any, Tuple, List
from .base import BaseConnector


class SQLiteConnector(BaseConnector):
    """Conector para bases de datos SQLite"""

    def __init__(self):
        super().__init__()
        self.db_path = None

    def connect(self, **kwargs) -> bool:
        """
        Conecta a una base de datos SQLite
        
        Parámetros:
            db_path: ruta del archivo .db
        """
        db_path = kwargs.get('db_path')
        if not db_path:
            raise ValueError("Se requiere db_path")

        try:
            # isolation_level=None activa el modo autocommit nativo de sqlite3
            # Esto permite usar BEGIN, COMMIT y ROLLBACK explícitamente sin interferencias del driver.
            self.connection = sqlite3.connect(db_path, isolation_level=None)
            self.cursor = self.connection.cursor()
            self.is_connected = True
            self.db_path = db_path
            return True
        except sqlite3.Error as e:
            raise Exception(f"Error conectando a SQLite: {e}")

    def disconnect(self) -> bool:
        """Cierra la conexión"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.connection:
                self.connection.close()
            self.is_connected = False
            return True
        except Exception as e:
            raise Exception(f"Error desconectando: {e}")

    def execute_query(self, sql: str) -> Tuple[bool, Any, str]:
        """
        Ejecuta una consulta SQL
        
        Retorna:
            (éxito, resultados, mensaje_error)
        """
        if not self.is_connected:
            return False, None, "No hay conexión activa"

        try:
            self.cursor.execute(sql)
            
            # Si la consulta devuelve filas
            if self.cursor.description:
                rows = self.cursor.fetchall()
                columns = [desc[0] for desc in self.cursor.description]
                return True, {'columns': columns, 'rows': rows}, ""
            else:
                # Comandos que no devuelven filas
                affected = self.cursor.rowcount
                return True, {'affected_rows': affected}, ""
                
        except sqlite3.Error as e:
            return False, None, str(e)

    def get_tables(self) -> Tuple[bool, List[str], str]:
        """Obtiene lista de tablas en la base de datos"""
        if not self.is_connected:
            return False, [], "No hay conexión activa"

        try:
            self.cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            tables = [row[0] for row in self.cursor.fetchall()]
            return True, tables, ""
        except sqlite3.Error as e:
            return False, [], str(e)

    def get_type(self) -> str:
        """Retorna el tipo de base de datos"""
        return "SQLite"

    def get_info(self) -> str:
        """Retorna información de la conexión"""
        return self.db_path if self.db_path else "Desconocido"