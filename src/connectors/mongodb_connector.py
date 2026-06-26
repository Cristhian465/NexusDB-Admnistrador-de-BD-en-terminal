import ast
from typing import Any, Tuple, List
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from .nosql_base import BaseNoSQLConnector

class MongoDBConnector(BaseNoSQLConnector):
    """Conector para MongoDB"""

    def __init__(self):
        super().__init__()
        self.client = None
        self.db = None
        self.db_name = ""
        self.host = ""
        self.port = 27017

    def connect(self, **kwargs) -> bool:
        try:
            self.db_name = kwargs.get('db_name')
            self.host = kwargs.get('host', 'localhost')
            self.port = int(kwargs.get('port', 27017))
            
            uri = f"mongodb://{self.host}:{self.port}/"
            self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            # Verifica la conexión
            self.client.server_info()
            self.db = self.client[self.db_name]
            self.is_connected = True
            return True
        except Exception as e:
            raise ConnectionError(f"No se pudo conectar a MongoDB: {str(e)}")

    def disconnect(self) -> bool:
        if self.client:
            self.client.close()
            self.is_connected = False
        return True

    def _parse_dict(self, text: str) -> dict:
        """Intenta parsear un string como diccionario Python (soporta comillas simples) o JSON"""
        if not text or text.strip() == "":
            return {}
        try:
            return ast.literal_eval(text)
        except Exception:
            raise ValueError(f"Filtro o documento inválido, no es un formato JSON/Diccionario válido: {text}")

    def execute_query(self, sql: str) -> Tuple[bool, Any, str]:
        """
        Adapta la ejecución a comandos NoSQL de MongoDB.
        Formatos soportados:
        - find <coleccion> [<filtro>]
        - insert <coleccion> <documento>
        - update <coleccion> <filtro> <set>
        - delete <coleccion> <filtro>
        """
        if not self.is_connected:
            return False, None, "No hay conexión a MongoDB"

        parts = sql.strip().split(maxsplit=2)
        if len(parts) < 2:
            return False, None, "Comando incompleto. Uso: <operacion> <coleccion> [parametros]"

        op = parts[0].lower()
        coll_name = parts[1]
        params_str = parts[2] if len(parts) > 2 else "{}"

        try:
            collection = self.db[coll_name]

            if op == "find":
                query = self._parse_dict(params_str)
                cursor = collection.find(query)
                results = list(cursor)
                if not results:
                    return True, {"columns": [], "rows": []}, ""
                
                # Extraer todas las claves posibles (schema dinámico)
                keys = set()
                for doc in results:
                    keys.update(doc.keys())
                columns = sorted(list(keys))
                
                # Formatear filas asegurando el orden de columnas
                rows = []
                for doc in results:
                    rows.append([str(doc.get(col, "")) for col in columns])
                    
                return True, {"columns": columns, "rows": rows}, ""

            elif op == "insert":
                doc = self._parse_dict(params_str)
                if not doc:
                    return False, None, "Documento a insertar no puede estar vacío"
                res = collection.insert_one(doc)
                return True, {"affected_rows": 1, "inserted_id": str(res.inserted_id)}, ""

            elif op == "update":
                # update coleccion {"filtro": 1} {"$set": {"a": 2}}
                # Necesitamos dividir los parámetros en dos diccionarios.
                # Como usar split es frágil con JSON, buscamos el cierre del primer dict
                bracket_count = 0
                split_idx = -1
                for i, char in enumerate(params_str):
                    if char == '{': bracket_count += 1
                    elif char == '}': 
                        bracket_count -= 1
                        if bracket_count == 0:
                            split_idx = i
                            break
                if split_idx == -1 or split_idx == len(params_str) - 1:
                    return False, None, "Formato update inválido. Uso: update <coleccion> <filtro> <set>"
                
                filter_str = params_str[:split_idx+1]
                set_str = params_str[split_idx+1:].strip()
                
                filter_doc = self._parse_dict(filter_str)
                set_doc = self._parse_dict(set_str)
                
                # Si el usuario no puso modificadores (ej: $set), lo asumimos
                if not any(k.startswith('$') for k in set_doc.keys()):
                    set_doc = {"$set": set_doc}
                    
                res = collection.update_many(filter_doc, set_doc)
                return True, {"affected_rows": res.modified_count}, ""

            elif op == "delete":
                query = self._parse_dict(params_str)
                res = collection.delete_many(query)
                return True, {"affected_rows": res.deleted_count}, ""

            else:
                return False, None, f"Operación no soportada en MongoDB: {op}"

        except Exception as e:
            return False, None, str(e)

    def list_collections(self) -> Tuple[bool, List[str], str]:
        if not self.is_connected:
            return False, [], "No hay conexión a MongoDB"
        try:
            return True, self.db.list_collection_names(), ""
        except Exception as e:
            return False, [], str(e)

    def get_type(self) -> str:
        return "MongoDB"

    def get_info(self) -> str:
        return f"{self.host}:{self.port}/{self.db_name}"
