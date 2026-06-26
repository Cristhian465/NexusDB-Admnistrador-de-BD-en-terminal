import json
import os
import re
import sqlite3
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
from sqlalchemy import create_engine, text


class CargadorDestino:
    """Carga datos en un SQLite intermedio y exporta al formato del motor destino."""

    INTEGER_TYPES = ("INT", "SERIAL", "BIGINT", "SMALLINT")
    REAL_TYPES = ("REAL", "FLOAT", "DOUBLE", "NUMERIC", "DECIMAL")
    BLOB_TYPES = ("BLOB", "BINARY", "BYTES")

    def __init__(self, motor_destino: str):
        self.motor = motor_destino
        self.tabla_a_esquema: Dict[str, str] = {}
        self._tabla_export_map: Dict[str, Dict[str, str]] = {}
        self._stored_objs = {
            "vistas": [],
            "triggers": [],
            "procedimientos": [],
            "funciones": [],
            "indices": [],
        }

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        upload_dir = os.path.join(base_dir, "uploads")
        os.makedirs(upload_dir, exist_ok=True)

        nombre_archivo = f"migracion_{motor_destino.lower().replace(' ', '_')}.db"
        self.ruta_salida = os.path.join(upload_dir, nombre_archivo)
        self.engine = create_engine(f"sqlite:///{self.ruta_salida}")

    @staticmethod
    def _nombre_seguro(nombre: str) -> str:
        return str(nombre).replace(" ", "_").replace("-", "_").replace(".", "_")

    @staticmethod
    def _quote_ident(ident: str, motor: str) -> str:
        m = (motor or "").lower()
        if "mysql" in m or "mariadb" in m:
            return f"`{ident}`"
        if "sql server" in m or "microsoft sql server" in m or "azure sql" in m:
            return f"[{ident}]"
        if "bigquery" in m:
            return f"`{ident}`"
        # Snowflake, Redshift, Db2, Oracle, Postgres, SQLite: double quotes
        return f'"{ident}"'

    def _qualified_name(self, schema: str, table: str, motor: str) -> str:
        s = self._nombre_seguro(schema or "public")
        t = self._nombre_seguro(table)
        if "sqlite" in (motor or "").lower():
            return self._quote_ident(f"{s}_{t}", motor)
        return f"{self._quote_ident(s, motor)}.{self._quote_ident(t, motor)}"

    @staticmethod
    def _sql_literal(v: Any) -> str:
        if v is None:
            return "NULL"
        if isinstance(v, (int, float)):
            return str(v)
        return "'" + str(v).replace("'", "''") + "'"

    def _tipo_sql_destino(self, tipo_origen: str, motor: str) -> str:
        t = (tipo_origen or "TEXT").upper()
        m = (motor or "").lower()

        if any(x in t for x in self.INTEGER_TYPES):
            if "oracle" in m:
                return "NUMBER"
            if "bigquery" in m:
                return "INT64"
            return "INTEGER"
        if any(x in t for x in self.REAL_TYPES):
            if "postgres" in m or "redshift" in m:
                return "DOUBLE PRECISION"
            if "oracle" in m:
                return "FLOAT"
            if "bigquery" in m:
                return "FLOAT64"
            if "snowflake" in m:
                return "FLOAT"
            return "REAL"
        if any(x in t for x in self.BLOB_TYPES):
            if "bigquery" in m:
                return "BYTES"
            if "snowflake" in m or "redshift" in m:
                return "VARIANT"
            return "BLOB"
        if "oracle" in m:
            return "VARCHAR2(4000)"
        if "postgres" in m or "redshift" in m:
            return "TEXT"
        if "bigquery" in m:
            return "STRING"
        if "snowflake" in m:
            return "VARCHAR"
        return "VARCHAR(4000)"

    def _adaptar_sql_objeto(self, sql: str, motor: str) -> str:
        if not sql:
            return ""
        s = sql.strip().replace("\r\n", "\n")
        m = (motor or "").lower()

        if "postgres" in m or "redshift" in m:
            s = re.sub(r"`([^`]+)`", r'"\\1"', s)
            s = re.sub(r"\[([^\]]+)\]", r'"\\1"', s)
            s = re.sub(r"\bAUTO_INCREMENT\b", "", s, flags=re.IGNORECASE)
        elif "mysql" in m or "mariadb" in m:
            s = re.sub(r"\[([^\]]+)\]", r"`\\1`", s)
            s = re.sub(r'"([^"]+)"', r"`\\1`", s)
        elif "sql server" in m or "microsoft sql server" in m or "azure sql" in m:
            s = re.sub(r"`([^`]+)`", r"[\\1]", s)
            s = re.sub(r'"([^"]+)"', r"[\\1]", s)
            s = re.sub(r"\bIF\s+NOT\s+EXISTS\b", "", s, flags=re.IGNORECASE)
        elif "oracle" in m:
            s = re.sub(r"`([^`]+)`", r'"\\1"', s)
            s = re.sub(r"\[([^\]]+)\]", r'"\\1"', s)
            s = re.sub(r"\bIF\s+NOT\s+EXISTS\b", "", s, flags=re.IGNORECASE)
        elif "snowflake" in m:
            # Snowflake usa double quotes pero es case-insensitive
            s = re.sub(r"`([^`]+)`", r'"\\1"', s)
            s = re.sub(r"\[([^\]]+)\]", r'"\\1"', s)
            s = re.sub(r"\bAUTO_INCREMENT\b", "", s, flags=re.IGNORECASE)
        elif "bigquery" in m:
            # BigQuery usa backticks
            s = re.sub(r'"([^"]+)"', r"`\\1`", s)
            s = re.sub(r"\[([^\]]+)\]", r"`\\1`", s)
        elif "db2" in m:
            # IBM Db2 usa comillas dobles
            s = re.sub(r"`([^`]+)`", r'"\\1"', s)
            s = re.sub(r"\[([^\]]+)\]", r'"\\1"', s)

        if not s.endswith(";"):
            s += ";"
        return s

    def crear_esquemas(self, esquemas_dict: Dict[str, List[str]]) -> int:
        # Motor real se resuelve en export; aquí solo contamos.
        return len([s for s in esquemas_dict.keys() if s and s != "public"])

    def crear_estructura(self, esquema: Dict[str, Any], tabla_a_esquema: Dict[str, str] = None) -> int:
        creadas = 0
        with self.engine.connect() as conn:
            for tabla, info in esquema.items():
                if "." in str(tabla):
                    esquema_detectado, nombre_base = str(tabla).split(".", 1)
                else:
                    esquema_detectado, nombre_base = "public", str(tabla)

                esquema_tabla = (tabla_a_esquema or {}).get(tabla) or esquema_detectado or "public"
                nombre_sqlite = self._nombre_seguro(f"{esquema_tabla}_{nombre_base}")

                self._tabla_export_map[nombre_sqlite] = {
                    "schema": esquema_tabla,
                    "table": nombre_base,
                }

                if isinstance(info, dict):
                    columnas = info.get("columnas", [])
                    pks = info.get("claves_primarias", [])
                    fks = info.get("claves_foraneas", [])
                    indices = info.get("indices", [])
                else:
                    columnas = info
                    pks = []
                    fks = []
                    indices = []

                if not columnas:
                    continue

                cols_sql = []
                for col in columnas:
                    col_nombre = self._nombre_seguro(col.get("nombre", "col"))
                    tipo_origen = str(col.get("tipo", "TEXT")).upper()
                    if any(t in tipo_origen for t in self.INTEGER_TYPES):
                        tipo_sql = "INTEGER"
                    elif any(t in tipo_origen for t in self.REAL_TYPES):
                        tipo_sql = "REAL"
                    elif any(t in tipo_origen for t in self.BLOB_TYPES):
                        tipo_sql = "BLOB"
                    else:
                        tipo_sql = "TEXT"
                    nullable = "" if col.get("nullable", True) else " NOT NULL"
                    cols_sql.append(f'"{col_nombre}" {tipo_sql}{nullable}')

                if pks:
                    pk_cols = ", ".join(f'"{self._nombre_seguro(p)}"' for p in pks)
                    cols_sql.append(f"PRIMARY KEY ({pk_cols})")

                for fk in fks:
                    fk_cols = ", ".join(f'"{self._nombre_seguro(c)}"' for c in fk.get("columnas", []))
                    ref_tabla = self._nombre_seguro(fk.get("tabla_ref", ""))
                    ref_cols = ", ".join(f'"{self._nombre_seguro(c)}"' for c in fk.get("columnas_ref", []))
                    if fk_cols and ref_tabla and ref_cols:
                        cols_sql.append(f'FOREIGN KEY ({fk_cols}) REFERENCES "{ref_tabla}" ({ref_cols})')

                sql = f'CREATE TABLE IF NOT EXISTS "{nombre_sqlite}" ({", ".join(cols_sql)})'
                try:
                    conn.execute(text(sql))
                    creadas += 1
                except Exception as e:
                    print(f"Aviso creando tabla {nombre_sqlite}: {e}")

                for idx in indices:
                    idx_nombre = self._nombre_seguro(idx.get("nombre") or f"idx_{nombre_sqlite}")
                    idx_cols = ", ".join(f'"{self._nombre_seguro(c)}"' for c in idx.get("columnas", []) if c)
                    if not idx_cols:
                        continue
                    unico = "UNIQUE " if idx.get("unico") else ""
                    sql_idx = f'CREATE {unico}INDEX IF NOT EXISTS "{idx_nombre}" ON "{nombre_sqlite}" ({idx_cols})'
                    try:
                        conn.execute(text(sql_idx))
                    except Exception as e:
                        print(f"Aviso creando indice {idx_nombre}: {e}")

            conn.commit()
        return creadas

    def cargar_tabla(self, tabla: str, df: pd.DataFrame) -> int:
        if df.empty:
            return 0

        esquema_tabla = self.tabla_a_esquema.get(tabla, "public")
        nombre_base = str(tabla).split(".")[-1]
        nombre_tabla = self._nombre_seguro(f"{esquema_tabla}_{nombre_base}")

        self._tabla_export_map[nombre_tabla] = {
            "schema": esquema_tabla,
            "table": nombre_base,
        }

        df = df.copy()
        df.columns = [self._nombre_seguro(c) for c in df.columns]
        try:
            df.to_sql(nombre_tabla, self.engine, if_exists="append", index=False)
            return len(df)
        except Exception as e:
            print(f"Error cargando {tabla}: {e}")
            return 0

    def generar_sql_dump(self) -> str:
        # Compatibilidad con llamadas existentes
        return self._generar_sql(self.motor)

    def _generar_sql(self, motor: str) -> str:
        if not os.path.exists(self.ruta_salida):
            return ""

        conn = sqlite3.connect(self.ruta_salida)
        cursor = conn.cursor()

        out = [
            "-- SQL Export generado por MigradorBD",
            f"-- Fecha: {datetime.now()}",
            f"-- Motor destino: {motor}",
            "",
        ]

        m = motor.lower()
        if "sqlite" not in m:
            schemas = sorted({
                v.get("schema", "public")
                for v in self._tabla_export_map.values()
                if v.get("schema") and v.get("schema") != "public"
            })
            for sch in schemas:
                if "oracle" in m:
                    out.append(f"-- Crear esquema/usuario manualmente si no existe: {sch}")
                else:
                    out.append(f"CREATE SCHEMA IF NOT EXISTS {self._quote_ident(sch, motor)};")
            if schemas:
                out.append("")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        for (tabla_sqlite,) in cursor.fetchall():
            map_info = self._tabla_export_map.get(tabla_sqlite, {"schema": "public", "table": tabla_sqlite})
            schema = map_info.get("schema", "public")
            table = map_info.get("table", tabla_sqlite)

            cursor.execute(f"PRAGMA table_info(`{tabla_sqlite}`)")
            cols_info = cursor.fetchall()

            cols_ddl = []
            pks = []
            for c in cols_info:
                col_name = c[1]
                col_type = c[2] or "TEXT"
                notnull = bool(c[3])
                is_pk = int(c[5]) > 0
                q_col = self._quote_ident(col_name, motor)
                t_sql = self._tipo_sql_destino(col_type, motor)
                col_def = f"{q_col} {t_sql}" + (" NOT NULL" if notnull else "")
                cols_ddl.append(col_def)
                if is_pk:
                    pks.append(col_name)

            if pks:
                cols_ddl.append("PRIMARY KEY (" + ", ".join(self._quote_ident(p, motor) for p in pks) + ")")

            q_name = self._qualified_name(schema, table, motor)
            out.append(f"CREATE TABLE IF NOT EXISTS {q_name} ({', '.join(cols_ddl)});")

            cursor.execute(f"SELECT * FROM `{tabla_sqlite}`")
            filas = cursor.fetchall()
            if filas:
                cols = [c[1] for c in cols_info]
                cols_sql = ", ".join(self._quote_ident(c, motor) for c in cols)
                for fila in filas:
                    vals = ", ".join(self._sql_literal(v) for v in fila)
                    out.append(f"INSERT INTO {q_name} ({cols_sql}) VALUES ({vals});")
            out.append("")

        for label, key in [
            ("Vistas importadas", "vistas"),
            ("Triggers importados", "triggers"),
            ("Procedimientos importados", "procedimientos"),
            ("Funciones importadas", "funciones"),
            ("Indices importados", "indices"),
        ]:
            objs = self._stored_objs.get(key, [])
            if not objs:
                continue
            out.append(f"-- {label}")
            for obj in objs:
                out.append(self._adaptar_sql_objeto(obj.get("sql", ""), motor))
            out.append("")

        conn.close()
        return "\n".join(out)

    def generar_export(self, motor: str = None) -> tuple:
        motor = (motor or self.motor or "").lower()

        if "sqlite" in motor:
            return (self.ruta_salida, ".db", "application/x-sqlite3", True)
        if any(x in motor for x in ["mysql", "postgres", "oracle", "sql server", "mariadb", "snowflake", "redshift", "db2", "azure sql", "bigquery"]):
            return (self._generar_sql(motor), ".sql", "application/sql", False)
        if "mongo" in motor:
            return (self._generar_json(), ".json", "application/json", False)
        if "elasticsearch" in motor:
            return (self._generar_ndjson(), ".ndjson", "application/x-ndjson", False)
        if "cassandra" in motor:
            return (self._generar_cql(), ".cql", "text/plain", False)
        if "redis" in motor:
            return (self._generar_redis(), ".redis", "text/plain", False)
        return (self._generar_json(), ".json", "application/json", False)

    def crear_vistas(self, vistas: List[Dict[str, str]]) -> int:
        return self._store_objs("vistas", vistas)

    def crear_triggers(self, triggers: List[Dict[str, str]]) -> int:
        return self._store_objs("triggers", triggers)

    def crear_procedimientos(self, procedimientos: List[Dict[str, str]]) -> int:
        return self._store_objs("procedimientos", procedimientos)

    def crear_funciones(self, funciones: List[Dict[str, str]]) -> int:
        return self._store_objs("funciones", funciones)

    def crear_indices(self, indices: List[Dict[str, str]]) -> int:
        return self._store_objs("indices", indices)

    def _store_objs(self, key: str, items: List[Dict[str, str]]) -> int:
        n = 0
        for it in items or []:
            sql = it.get("sql") if isinstance(it, dict) else str(it)
            if sql:
                self._stored_objs[key].append({"sql": sql})
                n += 1
        return n

    def _iter_tables(self):
        if not os.path.exists(self.ruta_salida):
            return []
        conn = sqlite3.connect(self.ruta_salida)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [r[0] for r in cur.fetchall()]
        conn.close()
        return tables

    def _generar_json(self) -> str:
        if not os.path.exists(self.ruta_salida):
            return ""

        conn = sqlite3.connect(self.ruta_salida)
        cur = conn.cursor()
        out = {
            "metadata": {
                "generator": "MigradorBD",
                "timestamp": datetime.now().isoformat(),
                "motor": self.motor,
            },
            "collections": {},
            "objects": self._stored_objs,
        }

        for tabla in self._iter_tables():
            cur.execute(f"PRAGMA table_info(`{tabla}`)")
            cols = [c[1] for c in cur.fetchall()]
            cur.execute(f"SELECT * FROM `{tabla}`")
            rows = cur.fetchall()
            out["collections"][tabla] = [dict(zip(cols, r)) for r in rows]

        conn.close()
        return json.dumps(out, ensure_ascii=False, indent=2, default=str)

    def _generar_ndjson(self) -> str:
        if not os.path.exists(self.ruta_salida):
            return ""

        conn = sqlite3.connect(self.ruta_salida)
        cur = conn.cursor()
        lines = []
        for tabla in self._iter_tables():
            cur.execute(f"PRAGMA table_info(`{tabla}`)")
            cols = [c[1] for c in cur.fetchall()]
            cur.execute(f"SELECT * FROM `{tabla}`")
            for i, row in enumerate(cur.fetchall()):
                lines.append(json.dumps({"index": {"_index": tabla, "_id": i}}))
                lines.append(json.dumps(dict(zip(cols, row)), ensure_ascii=False, default=str))

        # anexar objetos como metadatos NDJSON
        lines.append(json.dumps({"meta": {"objects": self._stored_objs}}, ensure_ascii=False))
        conn.close()
        return "\n".join(lines)

    def _generar_cql(self) -> str:
        if not os.path.exists(self.ruta_salida):
            return ""

        conn = sqlite3.connect(self.ruta_salida)
        cur = conn.cursor()
        out = [
            "-- CQL Script generado por MigradorBD",
            f"-- Fecha: {datetime.now()}",
            "",
        ]

        for tabla in self._iter_tables():
            cur.execute(f"PRAGMA table_info(`{tabla}`)")
            cols_info = cur.fetchall()
            cols = [c[1] for c in cols_info]

            cols_def = [f"  {c} text" for c in cols]
            pk = cols[0] if cols else "id"
            out.append(f"CREATE TABLE IF NOT EXISTS {tabla} (\n" + ",\n".join(cols_def) + f",\n  PRIMARY KEY ({pk})\n);")

            cur.execute(f"SELECT * FROM `{tabla}`")
            for row in cur.fetchall():
                out.append(
                    f"INSERT INTO {tabla} ({', '.join(cols)}) VALUES ({', '.join(self._sql_literal(v) for v in row)});"
                )
            out.append("")

        out.append("-- Objetos no-tabulares")
        out.append(json.dumps(self._stored_objs, ensure_ascii=False))

        conn.close()
        return "\n".join(out)

    def _generar_redis(self) -> str:
        if not os.path.exists(self.ruta_salida):
            return ""

        conn = sqlite3.connect(self.ruta_salida)
        cur = conn.cursor()
        out = [
            "# Redis commands generadas por MigradorBD",
            f"# Fecha: {datetime.now()}",
            "",
        ]

        for tabla in self._iter_tables():
            cur.execute(f"PRAGMA table_info(`{tabla}`)")
            cols = [c[1] for c in cur.fetchall()]
            cur.execute(f"SELECT * FROM `{tabla}`")
            for i, row in enumerate(cur.fetchall()):
                key = f"{tabla}:{i}"
                cmd = ["HSET", key]
                for c, v in zip(cols, row):
                    if v is not None:
                        cmd.append(c)
                        cmd.append(str(v).replace('"', '\\"'))
                out.append(" ".join(f'"{x}"' if " " in x else x for x in cmd))

        out.append("")
        out.append("# Objetos no-tabulares (json)")
        out.append("SET migrador:objects '" + json.dumps(self._stored_objs, ensure_ascii=False).replace("'", "\\'") + "'")

        conn.close()
        return "\n".join(out)

    def get_ruta_salida(self) -> str:
        return self.ruta_salida
