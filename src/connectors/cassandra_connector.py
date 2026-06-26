from cassandra.cluster import Cluster
from typing import Any, Tuple, List
from .nosql_base import BaseNoSQLConnector

class CassandraConnector(BaseNoSQLConnector):
    """Conector para Cassandra"""

    def __init__(self):
        super().__init__()
        self.cluster = None
        self.session = None
        self.host = ""
        self.keyspace = ""

    def connect(self, **kwargs) -> bool:
        try:
            self.host = kwargs.get('host', 'localhost')
            self.keyspace = kwargs.get('keyspace', '')
            
            self.cluster = Cluster([self.host])
            if self.keyspace:
                self.session = self.cluster.connect(self.keyspace)
            else:
                self.session = self.cluster.connect()
                
            self.is_connected = True
            return True
        except Exception as e:
            raise ConnectionError(f"No se pudo conectar a Cassandra: {str(e)}")

    def disconnect(self) -> bool:
        if self.cluster:
            self.cluster.shutdown()
            self.is_connected = False
        return True

    def execute_query(self, cql: str) -> Tuple[bool, Any, str]:
        """
        Ejecuta una consulta CQL (similar a SQL).
        """
        if not self.is_connected:
            return False, None, "No hay conexión a Cassandra"

        try:
            rows = self.session.execute(cql)
            results = list(rows)
            
            if not results:
                # Comandos como INSERT, UPDATE, DELETE
                if cql.strip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER")):
                    return True, {"affected_rows": 1}, ""
                return True, {"columns": [], "rows": []}, ""

            # Extraemos las columnas del primer registro (NamedTuple)
            columns = list(results[0]._fields)
            
            # Formateamos los datos
            table_rows = []
            for row in results:
                table_rows.append([str(getattr(row, col)) for col in columns])
                
            return True, {"columns": columns, "rows": table_rows}, ""

        except Exception as e:
            return False, None, str(e)

    def list_collections(self) -> Tuple[bool, List[str], str]:
        """Devuelve las tablas en el keyspace actual"""
        if not self.is_connected:
            return False, [], "No hay conexión a Cassandra"
        try:
            if not self.keyspace:
                return False, [], "No hay un keyspace seleccionado"
            
            query = f"SELECT table_name FROM system_schema.tables WHERE keyspace_name='{self.keyspace}';"
            rows = self.session.execute(query)
            tables = [row.table_name for row in rows]
            return True, tables, ""
        except Exception as e:
            return False, [], str(e)

    def get_type(self) -> str:
        return "Cassandra"

    def get_info(self) -> str:
        return f"{self.host} - KS: {self.keyspace}"
