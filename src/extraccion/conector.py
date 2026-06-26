import sqlite3
import pandas as pd
import json
import os
import re
from typing import Dict, Any, List, Optional
from sqlalchemy import create_engine, inspect, text

class ConectorOrigen:
    """Conecta y extrae datos de cualquier archivo de base de datos"""
    
    def __init__(self, ruta: str, tipo: str):
        self.ruta = ruta
        self.tipo = tipo
        self.engine = None
        self.tablas = []
        self.esquema = {}
        self.esquemas = {}  # Dict de esquemas: {nombre_esquema: [tablas]}
        self.tabla_a_esquema = {}  # Mapeo: tabla -> esquema
        self._sql_inserts = {}
        self._sql_contenido = ''
        self.triggers = []
        self.procedimientos = []
        self.vistas = []
        self.funciones = []
        self.indices = []
        
        try:
            if tipo == 'SQLite':
                self.engine = create_engine(f'sqlite:///{ruta}')
                self._descubrir_sqlite()
            elif tipo in ['PostgreSQL', 'MySQL', 'Microsoft SQL Server', 'Oracle', 'SQL Generico']:
                self._analizar_sql()
            elif tipo == 'MongoDB':
                self._cargar_json()
            elif tipo == 'CSV':
                self._cargar_csv()
            elif tipo == 'Excel':
                self._cargar_excel()
            elif tipo == 'Elasticsearch':
                self._cargar_json()
        except Exception as e:
            # Registrar pero no fallar completamente: inicializar con lista vacía
            print(f'[CONECTOR] Error inicializando {tipo}: {str(e)}')
    
    def _descubrir_sqlite(self):
        inspector = inspect(self.engine)
        self.tablas = [t for t in inspector.get_table_names() if not t.startswith('sqlite_')]

        for tabla in self.tablas:
            columnas = inspector.get_columns(tabla)
            pk_cols = inspector.get_pk_constraint(tabla).get('constrained_columns', [])
            fks = inspector.get_foreign_keys(tabla)
            indices = inspector.get_indexes(tabla)

            self.esquema[tabla] = {
                'columnas': [
                    {
                        'nombre': c['name'],
                        'tipo': str(c['type']),
                        'nullable': c.get('nullable', True),
                        'default': str(c['default']) if c.get('default') is not None else None,
                    }
                    for c in columnas
                ],
                'claves_primarias': pk_cols,
                'claves_foraneas': [
                    {
                        'columnas': fk['constrained_columns'],
                        'tabla_ref': fk['referred_table'],
                        'columnas_ref': fk['referred_columns'],
                    }
                    for fk in fks
                ],
                'indices': [
                    {
                        'nombre': idx['name'],
                        'columnas': idx['column_names'],
                        'unico': idx.get('unique', False),
                    }
                    for idx in indices
                ],
            }
        
        # Extraer vistas y triggers de SQLite
        with self.engine.connect() as conn:
            # Obtener vistas
            result = conn.execute(text("SELECT name, sql FROM sqlite_master WHERE type='view'"))
            for row in result:
                if row[1]:  # Si tiene SQL definition
                    self.vistas.append({'nombre': row[0], 'sql': row[1]})
            
            # Obtener triggers
            result = conn.execute(text("SELECT name, sql FROM sqlite_master WHERE type='trigger'"))
            for row in result:
                if row[1]:  # Si tiene SQL definition
                    self.triggers.append({'nombre': row[0], 'sql': row[1]})
    
    def _analizar_sql(self):
        # Intentar múltiples encodings para máxima compatibilidad
        contenido = ''
        for enc in ('utf-8', 'utf-16', 'latin-1'):
            try:
                with open(self.ruta, 'r', encoding=enc, errors='ignore') as f:
                    contenido = f.read()
                if 'CREATE TABLE' in contenido.upper() or 'INSERT INTO' in contenido.upper():
                    break
            except Exception:
                continue

        self._sql_contenido = contenido
        self._sql_inserts = {}
        self.tablas = []
        self.esquema = {}
        self.esquemas = {}
        self.tabla_a_esquema = {}

        # Parsear CREATE TABLE para extraer nombres de tablas Y esquemas
        # Captura: [esquema].[tabla] o esquema.tabla o solo tabla
        create_table_pattern = r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:[`"\[]?([A-Za-z0-9_]+)[`"\]]?\.)?[`"\[]?([A-Za-z0-9_]+)[`"\]]?'
        for match in re.finditer(create_table_pattern, contenido, re.IGNORECASE):
            esquema_nombre = match.group(1) if match.group(1) else 'public'  # Esquema por defecto
            tabla = match.group(2)
            fq = f"{esquema_nombre}.{tabla}"

            if fq and fq not in self.tablas:
                self.tablas.append(fq)
                self.tabla_a_esquema[fq] = esquema_nombre

                # Registrar esquema
                if esquema_nombre not in self.esquemas:
                    self.esquemas[esquema_nombre] = []
                self.esquemas[esquema_nombre].append(fq)

                self.esquema[fq] = {
                    'columnas': [],
                    'claves_primarias': [],
                    'claves_foraneas': [],
                    'indices': [],
                    'esquema': esquema_nombre,
                    'nombre': tabla,
                }

        # Parsear INSERT INTO para obtener columnas y datos
        # Patrón que captura: INSERT INTO [esquema.]tabla (cols) VALUES (valores);
        insert_pattern = r'INSERT\s+INTO\s+(?:[`"\[]?([A-Za-z0-9_]+)[`"\]]?\.)?[`"\[]?([A-Za-z0-9_]+)[`"\]]?\s*\((.*?)\)\s*VALUES\s*(.*?)(?:;|(?=\n\s*--|$))'
        
        for match in re.finditer(insert_pattern, contenido, re.IGNORECASE | re.DOTALL):
            esquema_nombre = match.group(1) if match.group(1) else 'public'
            tabla = match.group(2)
            fq = f"{esquema_nombre}.{tabla}"
            cols_raw = match.group(3)
            values_raw = match.group(4)
            
            # Limpiar nombres de columnas
            columnas = [self._limpiar_sql_identificador(c) for c in cols_raw.split(',') if c.strip()]
            
            # Parsear todas las filas (pueden ser múltiples en una sola sentencia)
            filas = self._extraer_todas_las_filas(values_raw)
            
            if fq not in self.tablas:
                self.tablas.append(fq)
                self.tabla_a_esquema[fq] = esquema_nombre

                # Registrar esquema
                if esquema_nombre not in self.esquemas:
                    self.esquemas[esquema_nombre] = []
                self.esquemas[esquema_nombre].append(fq)

                self.esquema[fq] = {
                    'columnas': [],
                    'claves_primarias': [],
                    'claves_foraneas': [],
                    'indices': [],
                    'esquema': esquema_nombre,
                    'nombre': tabla,
                }

            if filas:
                info = self._sql_inserts.setdefault(fq, {'columnas': columnas, 'filas': []})
                if not info['columnas'] and columnas:
                    info['columnas'] = columnas
                info['filas'].extend(filas)

                # Actualizar esquema con las columnas encontradas
                if not self.esquema[fq]['columnas']:
                    self.esquema[fq]['columnas'] = [
                        {'nombre': c, 'tipo': 'TEXT', 'nullable': True, 'default': None}
                        for c in columnas
                    ]
        
        # Extraer vistas, triggers, procedimientos y funciones
        self._extraer_objetos_db(contenido)

    def _extraer_todas_las_filas(self, values_raw: str) -> List[List[Any]]:
        """Extrae todas las filas de un bloque VALUES"""
        filas = []
        buffer = []
        en_cadena = False
        escape = False
        profundidad = 0
        
        for caracter in values_raw:
            if en_cadena:
                buffer.append(caracter)
                if escape:
                    escape = False
                elif caracter == '\\':
                    escape = True
                elif caracter == "'":
                    en_cadena = False
                continue
            
            if caracter == "'":
                en_cadena = True
                buffer.append(caracter)
                continue
                
            if caracter == '(':
                if profundidad == 0:
                    buffer = []
                else:
                    buffer.append(caracter)
                profundidad += 1
                continue
                
            if caracter == ')':
                profundidad -= 1
                if profundidad == 0:
                    fila_texto = ''.join(buffer).strip()
                    if fila_texto:
                        campos = self._separar_sql_campos(fila_texto)
                        fila_datos = [self._parsear_sql_literal(campo) for campo in campos]
                        if fila_datos:
                            filas.append(fila_datos)
                    buffer = []
                else:
                    buffer.append(caracter)
                continue
                
            if profundidad > 0:
                buffer.append(caracter)
        
        return filas

    @staticmethod
    def _limpiar_sql_identificador(valor: str) -> str:
        return str(valor).strip().strip('`"[]')

    @staticmethod
    def _parsear_sql_literal(token: str):
        token = token.strip()
        if not token or token.upper() == 'NULL':
            return None
        if token.lower().startswith("b'") and token.endswith("'"):
            token = token[2:-1]
        if token.startswith("'") and token.endswith("'"):
            valor = token[1:-1]
            valor = valor.replace("\\'", "'").replace("''", "'")
            valor = valor.replace('\\n', '\n').replace('\\r', '\r').replace('\\t', '\t')
            return valor
        if re.fullmatch(r'-?\d+', token):
            try:
                return int(token)
            except Exception:
                return token
        if re.fullmatch(r'-?\d+\.\d+', token):
            try:
                return float(token)
            except Exception:
                return token
        return token

    def _separar_sql_campos(self, fila: str) -> List[str]:
        campos = []
        actual = []
        en_cadena = False
        escape = False
        profundidad = 0

        for caracter in fila:
            if en_cadena:
                actual.append(caracter)
                if escape:
                    escape = False
                elif caracter == '\\':
                    escape = True
                elif caracter == "'":
                    en_cadena = False
                continue

            if caracter == "'":
                en_cadena = True
                actual.append(caracter)
                continue
            if caracter == '(':
                profundidad += 1
                actual.append(caracter)
                continue
            if caracter == ')':
                profundidad = max(0, profundidad - 1)
                actual.append(caracter)
                continue
            if caracter == ',' and profundidad == 0:
                campos.append(''.join(actual).strip())
                actual = []
                continue
            actual.append(caracter)

        if actual:
            campos.append(''.join(actual).strip())
        return campos

    def _parsear_sql_values(self, values_raw: str) -> List[List[Any]]:
        filas = []
        fila_actual = []
        buffer = []
        en_cadena = False
        escape = False
        profundidad = 0

        for caracter in values_raw:
            if en_cadena:
                buffer.append(caracter)
                if escape:
                    escape = False
                elif caracter == '\\':
                    escape = True
                elif caracter == "'":
                    en_cadena = False
                continue

            if caracter == "'":
                en_cadena = True
                buffer.append(caracter)
                continue
            if caracter == '(':
                if profundidad == 0:
                    buffer = []
                else:
                    buffer.append(caracter)
                profundidad += 1
                continue
            if caracter == ')':
                profundidad -= 1
                if profundidad == 0:
                    fila = ''.join(buffer).strip()
                    if fila:
                        campos = self._separar_sql_campos(fila)
                        fila_actual = [self._parsear_sql_literal(campo) for campo in campos]
                        filas.append(fila_actual)
                    buffer = []
                    fila_actual = []
                else:
                    buffer.append(caracter)
                continue
            if profundidad > 0:
                buffer.append(caracter)

        return filas
    
    def _cargar_json(self):
        with open(self.ruta, 'r', encoding='utf-8') as f:
            datos = json.load(f)

        if isinstance(datos, list):
            self.tablas = ['documentos']
            if datos:
                cols = [
                    {'nombre': k, 'tipo': str(type(v).__name__), 'nullable': True, 'default': None}
                    for k, v in datos[0].items()
                ]
            else:
                cols = []
            self.esquema = {
                'documentos': {
                    'columnas': cols,
                    'claves_primarias': [],
                    'claves_foraneas': [],
                    'indices': [],
                }
            }
            self._datos_json = datos
        else:
            self.tablas = ['datos']
            self.esquema = {
                'datos': {
                    'columnas': [{'nombre': 'contenido', 'tipo': 'JSON', 'nullable': True, 'default': None}],
                    'claves_primarias': [],
                    'claves_foraneas': [],
                    'indices': [],
                }
            }
    
    def _cargar_csv(self):
        nombre = os.path.splitext(os.path.basename(self.ruta))[0]
        self.tablas = [nombre]
        df = pd.read_csv(self.ruta, nrows=1)
        self.esquema = {
            nombre: {
                'columnas': [
                    {'nombre': col, 'tipo': str(df[col].dtype), 'nullable': True, 'default': None}
                    for col in df.columns
                ],
                'claves_primarias': [],
                'claves_foraneas': [],
                'indices': [],
            }
        }

    def _cargar_excel(self):
        xls = pd.ExcelFile(self.ruta)
        self.tablas = xls.sheet_names

        for hoja in self.tablas:
            df = pd.read_excel(self.ruta, sheet_name=hoja, nrows=1)
            self.esquema[hoja] = {
                'columnas': [
                    {'nombre': col, 'tipo': str(df[col].dtype), 'nullable': True, 'default': None}
                    for col in df.columns
                ],
                'claves_primarias': [],
                'claves_foraneas': [],
                'indices': [],
            }
    
    def _extraer_objetos_db(self, contenido: str):
        """Extrae vistas, triggers, procedimientos y funciones del SQL"""
        # Procesar el SQL para respetar cambios de DELIMITER y bloques $$ (Postgres)
        current_delim = ';'
        pos = 0
        length = len(contenido)

        def next_index(substr, start):
            idx = contenido.find(substr, start)
            return idx if idx != -1 else None

        while pos < length:
            # Buscar DELIMITER (MySQL) en la línea actual
            m = re.match(r'\s*DELIMITER\s+(.+)\s*\n', contenido[pos:], re.IGNORECASE)
            if m:
                token = m.group(1).strip()
                current_delim = token
                # avanzar pos
                pos += m.end()
                continue

            # Buscar siguiente CREATE (VIEW/TRIGGER/PROCEDURE/FUNCTION)
            m_create = re.search(r'CREATE\s+(OR\s+REPLACE\s+)?(VIEW|TRIGGER|PROCEDURE|FUNCTION)\b', contenido[pos:], re.IGNORECASE)
            if not m_create:
                break

            start = pos + m_create.start()
            # Encontrar nombre (simple heurística: la siguiente palabra tras el tipo)
            m_name = re.search(r'(VIEW|TRIGGER|PROCEDURE|FUNCTION)\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"\[]?([A-Za-z0-9_\.]+)[`"\]]?', contenido[start:], re.IGNORECASE)
            nombre = None
            tipo_obj = m_create.group(2).upper()
            if m_name:
                nombre = m_name.group(2)

            # Buscar fin de la sentencia respetando current_delim y bloques $$
            # Primero, buscar la siguiente ocurrencia del current_delim
            idx_delim = contenido.find(current_delim, start)
            idx_dollar = contenido.find('$$', start)

            end_pos = None
            if idx_dollar != -1 and (idx_delim == -1 or idx_dollar < idx_delim):
                # Hay bloque $$ antes del primer delimitador -> buscar siguiente $$ par
                idx_dollar_end = contenido.find('$$', idx_dollar + 2)
                if idx_dollar_end != -1:
                    # buscar el delimitador después del cierre $$
                    idx_delim_after = contenido.find(current_delim, idx_dollar_end + 2)
                    if idx_delim_after != -1:
                        end_pos = idx_delim_after + len(current_delim)
                    else:
                        end_pos = idx_dollar_end + 2
                else:
                    # no encontramos cierre $$; tomar hasta siguiente delim o EOF
                    end_pos = idx_delim + len(current_delim) if idx_delim != -1 else length
            else:
                # No $$ problemático; si la sentencia contiene BEGIN, intentar cerrar en END + delim
                segment_until_delim = contenido[start: idx_delim] if idx_delim != -1 else contenido[start:]
                if re.search(r'\bBEGIN\b', segment_until_delim, re.IGNORECASE):
                    # buscar el END que cierra el bloque
                    m_end = re.search(r'\bEND\b', contenido[start:], re.IGNORECASE)
                    if m_end:
                        # luego encontrar delimiter after END
                        idx_end_abs = start + m_end.end()
                        idx_delim_after = contenido.find(current_delim, idx_end_abs)
                        if idx_delim_after != -1:
                            end_pos = idx_delim_after + len(current_delim)
                if end_pos is None:
                    end_pos = idx_delim + len(current_delim) if idx_delim != -1 else length

            stmt = contenido[start:end_pos].strip() if end_pos else contenido[start:].strip()

            # Normalizar y almacenar según tipo
            try:
                if tipo_obj == 'VIEW':
                    # extraer el SQL completo
                    nombre_simple = nombre.split('.')[-1] if nombre else None
                    self.vistas.append({'nombre': nombre_simple or '', 'sql': stmt})
                elif tipo_obj == 'TRIGGER':
                    nombre_simple = nombre.split('.')[-1] if nombre else None
                    self.triggers.append({'nombre': nombre_simple or '', 'sql': stmt})
                elif tipo_obj in ('PROCEDURE', 'FUNCTION'):
                    nombre_simple = nombre.split('.')[-1] if nombre else None
                    obj = {'nombre': nombre_simple or '', 'tipo': tipo_obj, 'sql': stmt}
                    # clasificar en procedimientos o funciones
                    if tipo_obj == 'PROCEDURE':
                        self.procedimientos.append(obj)
                    else:
                        self.funciones.append(obj)
            except Exception:
                pass

            # avanzar pos
            pos = end_pos if end_pos else start + 1

        # Extraer CREATE INDEX por separado
        index_pattern = r'CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"\[]?([A-Za-z0-9_\.]+)[`"\]]?\s+ON\s+.*?(?:;|\Z)'
        for m_idx in re.finditer(index_pattern, contenido, re.IGNORECASE | re.DOTALL):
            nombre_idx = (m_idx.group(1) or '').split('.')[-1]
            sql_idx = m_idx.group(0).strip()
            if sql_idx:
                self.indices.append({'nombre': nombre_idx, 'sql': sql_idx})
    
    def extraer_datos_chunked(self, tabla: str, chunksize: int = 10000):
        """Generador que extrae datos de una tabla en bloques (chunks) para ahorrar memoria RAM."""
        if self.tipo == 'SQLite':
            nombre_real = tabla.split('.')[-1]
            try:
                for chunk in pd.read_sql(f'SELECT * FROM "{nombre_real}"', self.engine, chunksize=chunksize):
                    yield chunk
            except Exception as e:
                # Si falla, retornar vacio
                yield pd.DataFrame()
        elif self.tipo == 'CSV':
            try:
                for chunk in pd.read_csv(self.ruta, chunksize=chunksize):
                    yield chunk
            except Exception:
                for chunk in pd.read_csv(self.ruta, on_bad_lines='skip', engine='python', chunksize=chunksize):
                    yield chunk
        else:
            # Para el resto (SQL Generico, Excel, MongoDB) devolvemos todo en 1 solo chunk
            df = self.extraer_datos(tabla)
            if not df.empty:
                yield df
            else:
                yield pd.DataFrame()

    def extraer_datos(self, tabla: str) -> pd.DataFrame:
        """Extrae datos de una tabla especifica (legacy full load)"""
        if self.tipo == 'SQLite':
            nombre_real = tabla.split('.')[-1]
            return pd.read_sql(f'SELECT * FROM "{nombre_real}"', self.engine)
        elif self.tipo in ['PostgreSQL', 'MySQL', 'Microsoft SQL Server', 'Oracle', 'SQL Generico']:
            info = self._sql_inserts.get(tabla)
            if not info:
                if '.' not in tabla:
                    for k in self._sql_inserts.keys():
                        if k.endswith(f'.{tabla}'):
                            info = self._sql_inserts.get(k)
                            tabla = k
                            break
                else:
                    info = self._sql_inserts.get(tabla)

            if info and info.get('filas'):
                columnas = info.get('columnas') or [c['nombre'] for c in self.esquema.get(tabla, {}).get('columnas', [])]
                return pd.DataFrame(info['filas'], columns=columnas)

            esquema_info = self.esquema.get(tabla) or {}
            columnas = [c['nombre'] for c in esquema_info.get('columnas', [])] if esquema_info else []
            return pd.DataFrame(columns=columnas)
        elif self.tipo == 'CSV':
            try:
                return pd.read_csv(self.ruta)
            except Exception:
                return pd.read_csv(self.ruta, on_bad_lines='skip', engine='python')
        elif self.tipo == 'Excel':
            return pd.read_excel(self.ruta, sheet_name=tabla)
        elif self.tipo == 'MongoDB' and hasattr(self, '_datos_json'):
            return pd.DataFrame(self._datos_json)
        return pd.DataFrame()