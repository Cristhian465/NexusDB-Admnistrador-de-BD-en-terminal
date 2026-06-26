import redis
from typing import Any, Tuple, List
from .nosql_base import BaseNoSQLConnector

class RedisConnector(BaseNoSQLConnector):
    """Conector para Redis"""

    def __init__(self):
        super().__init__()
        self.client = None
        self.host = ""
        self.port = 6379
        self.db_index = 0

    def connect(self, **kwargs) -> bool:
        try:
            self.host = kwargs.get('host', 'localhost')
            self.port = int(kwargs.get('port', 6379))
            self.db_index = int(kwargs.get('db_index', 0))
            
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db_index,
                decode_responses=True, # Para recibir strings en vez de bytes
                socket_timeout=5
            )
            self.client.ping()
            self.is_connected = True
            return True
        except Exception as e:
            raise ConnectionError(f"No se pudo conectar a Redis: {str(e)}")

    def disconnect(self) -> bool:
        if self.client:
            self.client.close()
            self.is_connected = False
        return True

    def execute_query(self, command: str) -> Tuple[bool, Any, str]:
        """
        Ejecuta un comando raw de Redis (ej: SET clave valor, GET clave, KEYS *)
        """
        if not self.is_connected:
            return False, None, "No hay conexión a Redis"

        parts = command.strip().split()
        if not parts:
            return False, None, "Comando vacío"

        try:
            # Ejecutamos el comando directamente en el cliente redis
            result = self.client.execute_command(*parts)
            
            # Formateamos el resultado de salida para la tabla si es lista
            if isinstance(result, list):
                if len(result) == 0:
                    return True, [], ""
                return True, result, ""
            
            return True, result, ""

        except Exception as e:
            return False, None, str(e)

    def list_collections(self) -> Tuple[bool, List[str], str]:
        """En Redis, listamos algunas claves como equivalente a 'colecciones' o 'tablas'"""
        if not self.is_connected:
            return False, [], "No hay conexión a Redis"
        try:
            # Limitamos a las primeras 100 claves para no saturar si es muy grande
            keys = self.client.keys('*')
            return True, keys[:100], ""
        except Exception as e:
            return False, [], str(e)

    def get_type(self) -> str:
        return "Redis"

    def get_info(self) -> str:
        return f"{self.host}:{self.port} DB:{self.db_index}"
