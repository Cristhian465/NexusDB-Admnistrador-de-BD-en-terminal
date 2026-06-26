"""
Clase base para todos los conectores de base de datos
Define la interfaz que deben implementar
"""

from abc import ABC, abstractmethod
from typing import Any, Tuple, List


class BaseConnector(ABC):
    """Clase base abstracta para conectores de base de datos"""

    def __init__(self):
        self.connection = None
        self.cursor = None
        self.is_connected = False

    @abstractmethod
    def connect(self, **kwargs) -> bool:
        """Establece conexión con la base de datos"""
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """Cierra la conexión con la base de datos"""
        pass

    @abstractmethod
    def execute_query(self, sql: str) -> Tuple[bool, Any, str]:
        """
        Ejecuta una consulta SQL
        Retorna: (éxito, resultados, mensaje_error)
        """
        pass

    @abstractmethod
    def get_tables(self) -> Tuple[bool, List[str], str]:
        """Retorna lista de tablas en la base de datos"""
        pass

    @abstractmethod
    def get_type(self) -> str:
        """Retorna el tipo de base de datos (SQLite, PostgreSQL, MySQL)"""
        pass

    @abstractmethod
    def get_info(self) -> str:
        """Retorna información de la conexión actual"""
        pass