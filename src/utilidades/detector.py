import os
import json
import sqlite3
import re
import pandas as pd
from typing import Dict, Any, Optional, Tuple, List


def _extraer_texto_imprimible(datos: bytes, minimo: int = 6) -> str:
    """Extrae secuencias ASCII imprimibles para inspeccionar archivos binarios."""
    fragmentos = re.findall(rb"[ -~]{%d,}" % minimo, datos)
    if not fragmentos:
        return ""
    return "\n".join(fragmento.decode("latin-1", errors="ignore") for fragmento in fragmentos)


def _detectar_sql_desde_texto(texto: str) -> Tuple[str, str]:
    """Devuelve un tipo SQL estimado a partir de fragmentos de texto."""
    mayus = texto.upper()

    def _tiene_alguno(fragmentos):
        return any(fragmento in mayus for fragmento in fragmentos)

    # 1. Detección rápida por comentarios de cabecera de herramientas populares
    if 'HEIDISQL' in mayus:
        return 'MySQL', 'Dump de MySQL exportado con HeidiSQL'
    if 'MYSQL DUMP' in mayus or 'PG_DUMP' in mayus:
        if 'MYSQL DUMP' in mayus:
            return 'MySQL', 'Dump de MySQL oficial (mysqldump) detectado'
        if 'PG_DUMP' in mayus:
            return 'PostgreSQL', 'Dump de PostgreSQL (pg_dump) detectado'

    # 2. Detección por sintaxis de creación de tablas
    if 'CREATE TABLE' in mayus:
        if _tiene_alguno(['NVARCHAR', 'IDENTITY(', 'ON [PRIMARY]', '[DBO].']) or re.search(r'(^|\n)GO(\r?\n|$)', mayus) or '[' in texto:
            return 'Microsoft SQL Server', 'Dump SQL Server detectado'
        if _tiene_alguno(['POSTGRES', 'PG_', 'SERIAL', 'BIGSERIAL', 'SMALLSERIAL', 'NEXTVAL(', 'RETURNING', 'CREATE EXTENSION', 'SET SEARCH_PATH', 'ALTER TABLE ONLY', 'PG_CATALOG', 'OWNER TO']):
            return 'PostgreSQL', 'Dump PostgreSQL detectado'
        if _tiene_alguno(['AUTO_INCREMENT', 'ENGINE=INNODB', 'ENGINE=MYISAM', 'CHARACTER SET', 'COLLATE ', '/*!40101 SET']):
            return 'MySQL', 'Dump MySQL detectado'
        if 'VARCHAR2' in mayus or 'NUMBER(' in mayus or 'TABLESPACE' in mayus:
            return 'Oracle', 'Dump Oracle detectado'
        if 'INT64' in mayus or 'FLOAT64' in mayus or 'STRUCT<' in mayus:
            return 'Google BigQuery', 'Script BigQuery detectado'
        if 'VARIANT' in mayus or 'CLUSTER BY' in mayus:
            return 'Snowflake', 'Script Snowflake detectado'
        if 'DISTKEY' in mayus or 'SORTKEY' in mayus:
            return 'Amazon Redshift', 'Script Redshift detectado'
        if 'CLUSTERING ORDER BY' in mayus or 'WITH REPLICATION =' in mayus:
            return 'Apache Cassandra', 'Script Cassandra/CQL detectado'
        return 'SQL Generico', 'Script SQL detectado'

    # 3. Detección por sentencias DDL/DML sueltas o configuraciones
    if _tiene_alguno(['CREATE VIEW', 'CREATE TRIGGER', 'CREATE PROCEDURE', 'CREATE PROC', 'CREATE FUNCTION', 'CREATE INDEX', 'INSERT INTO']):
        if _tiene_alguno(['AUTO_INCREMENT', 'ENGINE=INNODB', '/*!40101 SET']):
            return 'MySQL', 'Dump MySQL detectado'
        if _tiene_alguno(['SERIAL', 'BIGSERIAL', 'SET SEARCH_PATH']):
            return 'PostgreSQL', 'Dump PostgreSQL detectado'
        return 'SQL Generico', 'Script SQL detectado parcialmente'
    
    # 4. Detectar CQL (Cassandra)
    if 'CREATE KEYSPACE' in mayus or ('CREATE TABLE' in mayus and 'CLUSTERING ORDER BY' in mayus):
        return 'Apache Cassandra', 'Script Cassandra detectado'

    return '', ''

class DetectorBaseDatos:
    """Detecta automaticamente el tipo de base de datos a partir del contenido del archivo."""

    @staticmethod
    def detectar(ruta: str, nombre: str) -> Tuple[str, str, Optional[Any]]:
        """
        Intenta detectar el tipo de base de datos a partir del contenido real del archivo,
        sin depender exclusivamente de la extension.
        Retorna: (tipo_detectado, mensaje, conexion_engine)
        """
        ext = os.path.splitext(nombre)[1].lower()

        # 1. Intentar SQLite (archivo binario): funciona con cualquier extension
        conn = None
        try:
            conn = sqlite3.connect(ruta)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tablas = cursor.fetchall()
            if tablas:
                return 'SQLite', f'SQLite: {len(tablas)} tablas', None
        except Exception:
            pass
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

        # 2. Intentar leer bytes y extraer texto imprimible para detectar scripts SQL (ANTES que JSON)
        try:
            with open(ruta, 'rb') as f:
                cabecera = f.read(2 * 1024 * 1024)

            texto_utf8 = cabecera.decode('utf-8', errors='ignore')

            # Intentar decodificación UTF-16 (algunos exportadores como MySQL Workbench usan UTF-16)
            texto_utf16 = ''
            if cabecera[:2] in (b'\xff\xfe', b'\xfe\xff'):
                try:
                    texto_utf16 = cabecera.decode('utf-16', errors='ignore')
                except Exception:
                    pass
            # Intentar latin-1 como fallback adicional
            texto_latin1 = cabecera.decode('latin-1', errors='ignore')

            texto_ascii = _extraer_texto_imprimible(cabecera)
            texto_muestra = f"{texto_utf8}\n{texto_utf16}\n{texto_latin1}\n{texto_ascii}"

            tipo_sql, mensaje_sql = _detectar_sql_desde_texto(texto_muestra)
            if tipo_sql:
                return tipo_sql, mensaje_sql, None

            if ext == '.bak':
                # Un .bak real de SQL Server suele ser binario; no se puede tratar como script SQL.
                no_texto = len(texto_ascii.strip()) < 100
                tiene_nulos = b'\x00' in cabecera
                if tiene_nulos or no_texto:
                    return 'SQL Server Backup', (
                        'El archivo .bak parece ser un backup binario de SQL Server. '
                        'Debe restaurarse en SQL Server y luego exportarse como script .sql para migrarlo.'
                    ), None
        except Exception as e:
            print(f'[DETECTOR] Error leyendo archivo para deteccion SQL: {str(e)}')

        # 3. Intentar JSON (MongoDB / Elasticsearch) - con validación más estricta
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                contenido = f.read()
            
            # Validar que comience como JSON (no como SQL)
            contenido_strip = contenido.strip()
            if contenido_strip.startswith('{') or contenido_strip.startswith('['):
                try:
                    datos = json.loads(contenido)
                    
                    # Validar que sea realmente un documento JSON de MongoDB/Elasticsearch
                    if isinstance(datos, list) and len(datos) > 0:
                        # Verificar si parece ser NDJSON (newline-delimited JSON)
                        if contenido.count('\n') > len(datos) * 0.5:
                            return 'MongoDB', f'NDJSON: {len(datos)} documentos', None
                        else:
                            return 'MongoDB', f'JSON array: {len(datos)} documentos', None
                            
                    elif isinstance(datos, dict):
                        # Elasticsearch tiene estructura característica
                        if '_source' in datos or 'hits' in datos or 'mappings' in datos or '_index' in datos:
                            return 'Elasticsearch', 'JSON Elasticsearch detectado', None
                        # MongoDB Atlas Export
                        if any(k in datos for k in ['_id', 'ObjectId', '__v']):
                            return 'MongoDB', 'JSON MongoDB detectado', None
                        # Genérico JSON
                        return 'MongoDB', 'JSON objeto detectado', None
                except json.JSONDecodeError:
                    # No es JSON válido, continuar con siguiente detección
                    pass
        except Exception:
            pass

        # 4. Intentar NDJSON (newline-delimited JSON) - MongoDB export format
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                primera_linea = f.readline().strip()
                if primera_linea.startswith('{') or primera_linea.startswith('['):
                    json.loads(primera_linea)
                    # Si la primera línea es JSON válido, probablemente sea NDJSON
                    f.seek(0)
                    lineas = f.readlines()
                    json_count = 0
                    for linea in lineas[:min(100, len(lineas))]:
                        try:
                            json.loads(linea.strip())
                            json_count += 1
                        except:
                            pass
                    if json_count > len(lineas) * 0.8:  # Si 80% de líneas son JSON
                        return 'MongoDB', f'NDJSON: ~{len(lineas)} documentos', None
        except Exception:
            pass

        # 5. Intentar CSV (por contenido, no solo por extension)
        try:
            df = pd.read_csv(ruta, nrows=5)
            if len(df.columns) >= 2:
                return 'CSV', f'CSV: {len(df.columns)} columnas', None
        except Exception:
            pass

        # 6. Intentar Excel
        try:
            with pd.ExcelFile(ruta) as xls:
                return 'Excel', f'Excel: {len(xls.sheet_names)} hojas', None
        except Exception:
            pass

        # 7. Último recurso: usar la extension como pista (con más tipos agregados)
        ext_map = {
            '.db': 'SQLite', '.sqlite': 'SQLite', '.sqlite3': 'SQLite',
            '.sql': 'SQL Generico', '.dump': 'SQL Generico', '.bak': 'SQL Generico',
            '.dmp': 'SQL Generico',
            '.json': 'MongoDB', '.bson': 'MongoDB',
            '.ndjson': 'MongoDB', '.jsonl': 'MongoDB',
            '.cql': 'Apache Cassandra', '.cqlsh': 'Apache Cassandra',
            '.csv': 'CSV', '.tsv': 'CSV',
            '.xlsx': 'Excel', '.xls': 'Excel', '.ods': 'Excel',
        }
        if ext in ext_map:
            tipo = ext_map[ext]
            return tipo, f'Tipo inferido por extensión ({ext}): {tipo}', None

        return 'Desconocido', (
            'No se pudo detectar el tipo de base de datos. '
            'Verifique que el archivo sea un formato soportado: '
            '.db, .sqlite, .sql, .dump, .json, .ndjson, .csv, .xlsx, .cql, etc.'
        ), None