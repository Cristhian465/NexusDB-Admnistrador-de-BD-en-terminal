import pandas as pd
from typing import Dict, Any, List

class MapeadorDatos:
    """Transforma datos para compatibilidad con destino"""
    
    @staticmethod
    def limpiar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """Limpia y prepara un DataFrame para migracion"""
        # Eliminar columnas con nombres problematicos
        df.columns = [str(c).replace(' ', '_').replace('-', '_').replace('.', '_') for c in df.columns]
        
        # Convertir tipos problematicos
        for col in df.columns:
            if df[col].dtype == 'object':
                try:
                    df[col] = df[col].astype(str)
                except:
                    pass
        
        # Eliminar filas completamente nulas
        df = df.dropna(how='all')
        
        return df
    
    @staticmethod
    def preparar_para_destino(df: pd.DataFrame, esquema_destino: Dict) -> pd.DataFrame:
        """Adapta DataFrame al esquema destino"""
        df = MapeadorDatos.limpiar_dataframe(df)
        
        # Si el destino tiene columnas especificas, mapear
        columnas_destino = list(esquema_destino.keys()) if esquema_destino else df.columns.tolist()
        
        # Mantener solo columnas que coincidan
        columnas_comunes = [c for c in df.columns if c in columnas_destino]
        if columnas_comunes:
            df = df[columnas_comunes]
        
        return df