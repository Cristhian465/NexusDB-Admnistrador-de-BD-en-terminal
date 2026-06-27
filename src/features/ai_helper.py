"""
Asistente inteligente: convierte texto en español a SQL.
"""

import re


def sugerir_sql(texto: str):
    """
    Convierte una frase en español a SQL.
    Retorna un string con la consulta SQL, o None si no se reconoce el patrón.
    """
    orig = texto.strip()           # texto original (preserva mayúsculas en valores)
    t    = orig.lower()            # versión en minúsculas para coincidencia de patrones

    # ── cuantos X hay ──────────────────────────────────────────────────────────
    m = re.match(r'cu[aá]ntos?\s+(\w+)\s+hay', t)
    if m:
        return f"SELECT COUNT(*) FROM {m.group(1)}"

    # ── muestra los N X mas ORDEN ──────────────────────────────────────────────
    m = re.match(
        r'muestra\s+los?\s+(\d+)\s+(\w+)\s+m[aá]s\s+'
        r'(caros?|baratos?|recientes?|antiguos?|grandes?|peque[ñn]os?|r[aá]pidos?)',
        t
    )
    if m:
        n, tabla, orden = m.group(1), m.group(2), m.group(3)
        campo = _inferir_campo(orden)
        desc = orden in ('caro', 'caros', 'reciente', 'recientes', 'grande', 'grandes', 'rapido', 'rápido')
        direccion = "DESC" if desc else "ASC"
        return f"SELECT * FROM {tabla} ORDER BY {campo} {direccion} LIMIT {n}"

    # ── elimina X donde Y es Z ─────────────────────────────────────────────────
    m = re.match(r'elimina\s+(\w+)\s+donde\s+(\w+)\s+es\s+(\S+)', t)
    if m:
        # Obtener los valores originales (posición en el texto original)
        mo = re.match(r'elimina\s+(\w+)\s+donde\s+(\w+)\s+es\s+(\S+)', orig, re.IGNORECASE)
        tabla, col, val = mo.group(1), mo.group(2), mo.group(3)
        return f"DELETE FROM {tabla} WHERE {col} = {_fmt(val)}"

    # ── actualiza X set Y a Z donde W es V ────────────────────────────────────
    m = re.match(
        r'actualiza\s+(\w+)\s+set\s+(\w+)\s+a\s+(\S+)\s+donde\s+(\w+)\s+es\s+(\S+)', t
    )
    if m:
        mo = re.match(
            r'actualiza\s+(\w+)\s+set\s+(\w+)\s+a\s+(\S+)\s+donde\s+(\w+)\s+es\s+(\S+)',
            orig, re.IGNORECASE
        )
        tabla, col_s, val_s, col_w, val_w = mo.groups()
        return f"UPDATE {tabla} SET {col_s} = {_fmt(val_s)} WHERE {col_w} = {_fmt(val_w)}"

    # ── inserta X col1 val1 col2 val2 … ───────────────────────────────────────
    m = re.match(r'inserta\s+(\w+)\s+(.+)', t)
    if m:
        mo = re.match(r'inserta\s+(\w+)\s+(.+)', orig, re.IGNORECASE)
        tabla = mo.group(1)
        tokens = mo.group(2).split()
        cols, vals = [], []
        i = 0
        while i + 1 < len(tokens):
            cols.append(tokens[i])
            vals.append(_fmt(tokens[i + 1]))
            i += 2
        if cols:
            return f"INSERT INTO {tabla} ({', '.join(cols)}) VALUES ({', '.join(vals)})"

    # ── muestra X donde Y es Z ─────────────────────────────────────────────────
    m = re.match(r'muestra\s+(\w+)\s+donde\s+(\w+)\s+es\s+(\S+)', t)
    if m:
        mo = re.match(r'muestra\s+(\w+)\s+donde\s+(\w+)\s+es\s+(\S+)', orig, re.IGNORECASE)
        tabla, col, val = mo.groups()
        return f"SELECT * FROM {tabla} WHERE {col} = {_fmt(val)}"

    # ── muestra X con Y mayor a Z ──────────────────────────────────────────────
    m = re.match(r'muestra\s+(\w+)\s+con\s+(\w+)\s+mayor\s+[aá]\s+(\S+)', t)
    if m:
        mo = re.match(r'muestra\s+(\w+)\s+con\s+(\w+)\s+mayor\s+[aá]\s+(\S+)', orig, re.IGNORECASE)
        tabla, col, val = mo.groups()
        return f"SELECT * FROM {tabla} WHERE {col} > {val}"

    # ── muestra X con Y menor a Z ──────────────────────────────────────────────
    m = re.match(r'muestra\s+(\w+)\s+con\s+(\w+)\s+menor\s+[aá]\s+(\S+)', t)
    if m:
        mo = re.match(r'muestra\s+(\w+)\s+con\s+(\w+)\s+menor\s+[aá]\s+(\S+)', orig, re.IGNORECASE)
        tabla, col, val = mo.groups()
        return f"SELECT * FROM {tabla} WHERE {col} < {val}"

    # ── muestra X ──────────────────────────────────────────────────────────────
    m = re.match(r'muestra\s+(\w+)', t)
    if m:
        return f"SELECT * FROM {m.group(1)}"

    return None


# ── helpers ────────────────────────────────────────────────────────────────────

def _fmt(val: str) -> str:
    """Formatea un valor: numérico sin comillas, texto con comillas simples."""
    try:
        float(val)
        return val
    except ValueError:
        return f"'{val}'"


def _inferir_campo(orden: str) -> str:
    mapa = {
        'caro': 'precio', 'caros': 'precio',
        'barato': 'precio', 'baratos': 'precio',
        'reciente': 'fecha', 'recientes': 'fecha',
        'antiguo': 'fecha', 'antiguos': 'fecha',
        'grande': 'tamanio', 'grandes': 'tamanio',
        'pequeño': 'tamanio', 'pequeños': 'tamanio',
        'rapido': 'velocidad', 'rápido': 'velocidad',
    }
    return mapa.get(orden, 'id')
