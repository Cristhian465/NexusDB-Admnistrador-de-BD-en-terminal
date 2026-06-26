from abc import abstractmethod
from typing import Any, Tuple, List
from .base import BaseConnector

class BaseNoSQLConnector(BaseConnector):
    """Clase base para conectores de bases de datos NoSQL.
    Hereda de BaseConnector para mantener la compatibilidad con el resto del proyecto,
    pero añade métodos más semánticos para NoSQL.
    """

    @abstractmethod
    def list_collections(self) -> Tuple[bool, List[str], str]:
        """
        Retorna lista de colecciones, claves o keyspaces dependiendo del motor.
        """
        pass

    def get_tables(self) -> Tuple[bool, List[str], str]:
        """
        Implementación de compatibilidad con BaseConnector.
        Llama internamente a list_collections.
        """
        return self.list_collections()
