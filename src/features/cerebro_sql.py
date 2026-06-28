"""
Cerebro SQL — traductor de lenguaje natural a SQL con un LLM.

Reemplaza/mejora al traductor por patrones (regex) de [ai_helper]: en lugar de
reconocer ~8 frases fijas, envía la frase del usuario MÁS el esquema real de la
base conectada a un modelo de lenguaje, que genera el SQL correcto para
cualquier redacción.

Soporta DOS proveedores y autodetecta cuál usar según la clave presente:
    - OpenAI  (ChatGPT)  -> variable OPENAI_API_KEY
    - Anthropic (Claude) -> variable ANTHROPIC_API_KEY

Diseño tolerante a fallos: si no hay librería/clave o la llamada falla, devuelve
None para que el llamador use el traductor por patrones como respaldo. Así la
demo nunca se queda sin respuesta.

Variables de entorno:
    OPENAI_API_KEY / ANTHROPIC_API_KEY   clave del proveedor (al menos una)
    NEXUS_AI_MODEL                       modelo a usar (opcional). Por defecto:
                                         gpt-4o-mini (OpenAI) o claude-opus-4-8 (Claude)
"""

import os
import re as _re

# ── Dependencias opcionales ──────────────────────────────────────────────────────
try:
    import openai
    _OPENAI_OK = True
except Exception:
    _OPENAI_OK = False

try:
    import anthropic
    _ANTHROPIC_OK = True
except Exception:
    _ANTHROPIC_OK = False

# Fallback por patrones (siempre disponible)
from features.ai_helper import sugerir_sql

_MODELO_DEFAULT = {"openai": "gpt-4o-mini", "anthropic": "claude-opus-4-8"}

_cliente = None
_cliente_proveedor = None


def proveedor() -> str:
    """Devuelve el proveedor de IA activo: 'openai', 'anthropic' o '' (ninguno)."""
    if _OPENAI_OK and os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if _ANTHROPIC_OK and os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return ""


def modelo() -> str:
    """Modelo a usar: el de NEXUS_AI_MODEL, o el por defecto del proveedor activo."""
    return os.environ.get("NEXUS_AI_MODEL") or _MODELO_DEFAULT.get(proveedor(), "")


def disponible() -> bool:
    """True si se puede usar el cerebro IA (librería instalada + clave presente)."""
    return proveedor() != ""


def motivo_no_disponible() -> str:
    if not (_OPENAI_OK or _ANTHROPIC_OK):
        return "No hay librería de IA instalada (pip install openai  o  anthropic)."
    return "Falta la clave de API (OPENAI_API_KEY o ANTHROPIC_API_KEY)."


def _get_cliente():
    """Crea (y cachea) el cliente del proveedor activo."""
    global _cliente, _cliente_proveedor
    prov = proveedor()
    if _cliente is None or _cliente_proveedor != prov:
        if prov == "openai":
            _cliente = openai.OpenAI()
        elif prov == "anthropic":
            _cliente = anthropic.Anthropic()
        else:
            _cliente = None
        _cliente_proveedor = prov
    return _cliente


# ── Extracción del esquema de la base conectada ─────────────────────────────────

def obtener_esquema(connector) -> str:
    """Devuelve una descripción de texto del esquema: tablas y sus columnas.

    Funciona en cualquier motor relacional usando 'SELECT * ... LIMIT 1' para leer
    los nombres de columna (no necesita catálogos específicos del motor).
    """
    if not connector or not connector.is_connected:
        return ""

    try:
        ok, tablas, _ = connector.get_tables()
        if not ok or not tablas:
            return ""
    except Exception:
        return ""

    lineas = []
    for tabla in tablas:
        cols = _columnas_de(connector, tabla)
        if cols:
            lineas.append(f"- {tabla}({', '.join(cols)})")
        else:
            lineas.append(f"- {tabla}")
    return "\n".join(lineas)


def _columnas_de(connector, tabla: str):
    """Obtiene las columnas de una tabla leyendo una fila de muestra."""
    try:
        ok, data, _ = connector.execute_query(f"SELECT * FROM {tabla} LIMIT 1")
        if ok and isinstance(data, dict) and data.get("columns"):
            return list(data["columns"])
    except Exception:
        pass
    return []


# ── Traducción texto → SQL con el LLM ────────────────────────────────────────────

_SISTEMA = (
    "Eres un traductor experto de lenguaje natural (español) a SQL. "
    "Recibes el ESQUEMA de una base de datos y una PETICIÓN del usuario. "
    "Devuelve ÚNICAMENTE una sentencia SQL válida para el motor indicado, sin "
    "explicaciones, sin comentarios y sin bloques de código markdown. "
    "Usa solo las tablas y columnas del esquema. Si la petición no se puede "
    "expresar como una sola consulta SQL sobre ese esquema, responde exactamente "
    "con NO_SQL."
)


def texto_a_sql(texto: str, esquema: str, dialecto: str = "SQLite"):
    """Traduce 'texto' a SQL usando el LLM activo. Retorna (sql, error).

    sql es None si no se pudo generar (y 'error' explica por qué) o si el modelo
    respondió NO_SQL.
    """
    if not disponible():
        return None, motivo_no_disponible()

    prompt = (
        f"Motor de base de datos: {dialecto}\n\n"
        f"ESQUEMA:\n{esquema or '(esquema no disponible)'}\n\n"
        f"PETICIÓN: {texto}\n\n"
        "Devuelve solo la sentencia SQL."
    )

    prov = proveedor()
    try:
        if prov == "openai":
            texto_sql = _llamar_openai(prompt)
        else:
            texto_sql = _llamar_anthropic(prompt)
    except Exception as e:
        return None, f"Error al consultar la IA ({prov}): {e}"

    texto_sql = _limpiar_sql(texto_sql or "")
    if not texto_sql or texto_sql.upper() == "NO_SQL":
        return None, "El modelo no pudo generar SQL para esa petición."
    return texto_sql, None


def _llamar_openai(prompt: str) -> str:
    resp = _get_cliente().chat.completions.create(
        model=modelo(),
        max_tokens=512,
        messages=[
            {"role": "system", "content": _SISTEMA},
            {"role": "user", "content": prompt},
        ],
    )
    return resp.choices[0].message.content or ""


def _llamar_anthropic(prompt: str) -> str:
    resp = _get_cliente().messages.create(
        model=modelo(),
        max_tokens=512,
        system=_SISTEMA,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in resp.content if b.type == "text")


def _limpiar_sql(texto: str) -> str:
    """Quita vallas de markdown (```sql ... ```) y espacios sobrantes."""
    t = texto.strip()
    m = _re.match(r"^```(?:sql)?\s*(.+?)\s*```$", t, _re.DOTALL | _re.IGNORECASE)
    if m:
        t = m.group(1).strip()
    return t.strip().rstrip(";").strip()


# ── Punto de entrada combinado: IA con respaldo por patrones ─────────────────────

def generar_sql(texto: str, connector=None, mode: str = "rel"):
    """Genera SQL desde lenguaje natural.

    Intenta primero el cerebro IA (con el esquema de la BD conectada); si no está
    disponible o falla, recurre al traductor por patrones de ai_helper.

    Retorna (sql, fuente) donde fuente es 'ia', 'regex' o None.
    """
    # El cerebro IA solo aplica a SQL relacional
    if mode == "rel" and disponible():
        dialecto = "SQLite"
        if connector and connector.is_connected:
            try:
                dialecto = connector.get_type()
            except Exception:
                pass
        esquema = obtener_esquema(connector)
        sql, _err = texto_a_sql(texto, esquema, dialecto)
        if sql:
            return sql, "ia"

    # Respaldo: patrones
    sql = sugerir_sql(texto)
    if sql:
        return sql, "regex"
    return None, None
