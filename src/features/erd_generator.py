"""
Generador de Diagramas Entidad-Relación (ERD) usando Mermaid.
"""
from rich import print as rprint

def generar_diagrama(connector) -> str:
    """Genera código Mermaid para un diagrama de la base de datos."""
    if not connector or not connector.is_connected:
        return ""
        
    db_type = connector.get_type().lower()
    
    success, tables, err = connector.get_tables()
    if not success or not tables:
        return ""
        
    mermaid = ["erDiagram"]
    
    for table in tables:
        # Obtener columnas
        query = f"SELECT * FROM {table} LIMIT 0"
        if "postgres" in db_type:
            query = f'SELECT * FROM "{table}" LIMIT 0'
            
        s, data, _ = connector.execute_query(query)
        columns = data.get("columns", []) if s and data else []
        
        mermaid.append(f"    {table} {{")
        for col in columns:
            mermaid.append(f"        string {col}")
        mermaid.append("    }")
        
    # Obtener relaciones (Foreign Keys) - Implementación básica
    if "sqlite" in db_type:
        for table in tables:
            s, data, _ = connector.execute_query(f"PRAGMA foreign_key_list('{table}')")
            if s and data and data.get("rows"):
                # cid, seq, table, from, to, on_update, on_delete, match
                for row in data["rows"]:
                    ref_table = row[2]
                    mermaid.append(f"    {ref_table} ||--o{{ {table} : relates_to")
    elif "postgres" in db_type:
        q = """
        SELECT
            tc.table_name AS table_name,
            ccu.table_name AS foreign_table_name
        FROM 
            information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
              AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY';
        """
        s, data, _ = connector.execute_query(q)
        if s and data and data.get("rows"):
            for row in data["rows"]:
                t1, t2 = row[0], row[1]
                mermaid.append(f"    {t2} ||--o{{ {t1} : relates_to")
                
    elif "mysql" in db_type:
        q = """
        SELECT 
            TABLE_NAME, REFERENCED_TABLE_NAME
        FROM
            INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE
            REFERENCED_TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL;
        """
        s, data, _ = connector.execute_query(q)
        if s and data and data.get("rows"):
            for row in data["rows"]:
                t1, t2 = row[0], row[1]
                mermaid.append(f"    {t2} ||--o{{ {t1} : relates_to")

    return "\n".join(mermaid)
