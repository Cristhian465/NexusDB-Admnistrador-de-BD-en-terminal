"""
Excepciones personalizadas para el proyecto
"""


class ConnectionError(Exception):
    """Error de conexión a la base de datos"""
    pass


class SyntaxError(Exception):
    """Error de sintaxis en el comando ingresado"""
    pass


class QueryError(Exception):
    """Error al ejecutar la consulta SQL"""
    pass 
