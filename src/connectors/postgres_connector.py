"""
Conector para PostgreSQL
"""

import psycopg2
from psycopg2 import Error
from typing import Any, Tuple, List
from .base import BaseConnector


class PostgresConnector(BaseConnector):
    """Conector para bases de datos PostgreSQL"""

    def __init__(self):
        super().__init__()
        self.dbname = None
        self.host = None
        self.user = None
        self.port = None

    def connect(self, **kwargs) -> bool:
        """
        Conecta a una base de datos PostgreSQL
        
        Parámetros:
            dbname: nombre de la base de datos
            user: nombre de usuario
            password: contraseña
            host: dirección del servidor (default: localhost)
            port: puerto (default: 5432)
        """
        self.dbname = kwargs.get('dbname')
        user = kwargs.get('user')
        password = kwargs.get('password')
        self.host = kwargs.get('host', 'localhost')
        self.port = kwargs.get('port', '5432')

        try:
            self.connection = psycopg2.connect(
                dbname=self.dbname,
                user=user,
                password=password,
                host=self.host,
                port=self.port
            )
            self.cursor = self.connection.cursor()
            self.is_connected = True
            self.user = user
            self.password = password
            return True
        except Error as e:
            raise Exception(f"Error conectando a PostgreSQL: {e}")

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
            
            # Si la consulta devuelve filas (como SELECT, SHOW, etc.)
            if self.cursor.description:
                rows = self.cursor.fetchall()
                columns = [desc[0] for desc in self.cursor.description]
                return True, {'columns': columns, 'rows': rows}, ""
            else:
                # Comandos que no devuelven filas (INSERT, UPDATE, DELETE, etc.)
                self.connection.commit()
                affected = self.cursor.rowcount
                return True, {'affected_rows': affected}, ""
                
        except Error as e:
            # En caso de error, intentamos hacer rollback para no dejar la transacción colgada
            if self.connection:
                self.connection.rollback()
            return False, None, str(e)

    def get_tables(self) -> Tuple[bool, List[str], str]:
        """Obtiene lista de tablas en la base de datos"""
        if not self.is_connected:
            return False, [], "No hay conexión activa"

        try:
            self.cursor.execute("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public'
            """)
            tables = [row[0] for row in self.cursor.fetchall()]
            return True, tables, ""
        except Error as e:
            return False, [], str(e)

    def get_type(self) -> str:
        """Retorna el tipo de base de datos"""
        return "PostgreSQL"

    def get_info(self) -> str:
        """Retorna información de la conexión"""
        return f"{self.dbname}@{self.host}:{self.port} (usuario: {self.user})"