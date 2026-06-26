# 🛡️ DBAdmin – Administrador de Bases de Datos por Consola

---

Página: http://147.93.7.122:8085

---

[![Python Version](https://img.shields.io/badge/Python-3.10-blue?logo=python)](https://python.org)
[![Build Status](https://img.shields.io/badge/Build-Passing-brightgreen)](https://github.com/TU_ORG/dbadmin/actions)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

> **Curso:** Base de Datos Avanzadas  
> **Proyecto:** DBAdmin – Herramienta CLI para la administración de bases de datos relacionales y NoSQL

---

## 📐 Arquitectura

```
v2Administrador de BD por consola o terminal/
├── main.py                     ← Punto de entrada principal
├── requirements.txt            ← Dependencias del proyecto
├── cli/                        ← Implementación de la interfaz de línea de comandos
│   ├── __init__.py
│   └── repl.py                 ← Bucle REPL para comandos interactivos
├── connectors/                 ← Conectores para bases de datos específicas
│   ├── __init__.py
│   ├── base.py                 ← Clase base para conectores
│   ├── cassandra_connector.py  ← Conector para Cassandra
│   ├── mongodb_connector.py    ← Conector para MongoDB
│   ├── mysql_connector.py      ← Conector para MySQL
│   ├── nosql_base.py           ← Clase base para NoSQL
│   ├── postgres_connector.py   ← Conector para PostgreSQL
│   ├── redis_connector.py      ← Conector para Redis
│   └── sqlite_connector.py     ← Conector para SQLite
├── core/                       ← Lógica principal del sistema
│   ├── __init__.py
│   ├── executor.py             ← Ejecutor de comandos
│   └── parser.py               ← Analizador de comandos
├── formatters/                 ← Formateadores de salida
│   ├── __init__.py
│   └── table_formatter.py      ← Formateador de tablas
├── utils/                      ← Utilidades y excepciones
│   ├── __init__.py
│   └── exceptions.py           ← Manejo de excepciones
├── assets/                     ← Recursos adicionales
├── build/                      ← Archivos generados durante la construcción
└── diagrams/                   ← Diagramas UML
    ├── activity_diagram.puml
    ├── class_diagram.puml
    └── sequence_diagram.puml
```

---

## 🚀 Inicio Rápido

```bash
# 1. Clonar el repositorio
git clone https://github.com/TU_ORG/dbadmin.git
cd dbadmin

# 2. Crear un entorno virtual e instalar dependencias
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Ejecutar la aplicación
python main.py
```

---

## 🧪 Ejecutar Pruebas

```bash
# Pruebas unitarias con pytest
pytest --tb=short

# Generar reporte de cobertura
pytest --cov=.
```

---

## 📦 Diagramas UML

El proyecto incluye diagramas UML para representar la arquitectura y el flujo del sistema.

- **Diagrama de Clases:** [class_diagram.puml](diagrams/class_diagram.puml)
- **Diagrama de Actividades:** [activity_diagram.puml](diagrams/activity_diagram.puml)
- **Diagrama de Secuencia:** [sequence_diagram.puml](diagrams/sequence_diagram.puml)

Para visualizar los diagramas, se recomienda usar [PlantUML](https://plantuml.com/).

---

## 🔍 Conectores Soportados

| Base de Datos   | Tipo       | Archivo Conector         |
|-----------------|------------|--------------------------|
| MySQL           | Relacional | `mysql_connector.py`     |
| PostgreSQL      | Relacional | `postgres_connector.py`  |
| SQLite          | Relacional | `sqlite_connector.py`    |
| MongoDB         | NoSQL      | `mongodb_connector.py`   |
| Cassandra       | NoSQL      | `cassandra_connector.py` |
| Redis           | NoSQL      | `redis_connector.py`     |

---

## 🔐 Configuración

El archivo `requirements.txt` incluye todas las dependencias necesarias para ejecutar el proyecto. Asegúrate de instalar las versiones especificadas para evitar problemas de compatibilidad.

---

## 👥 Equipo

**Curso:** Base de Datos Avanzadas  
**Universidad:** UPT – FAING – EPIS  
**Semestre:** 2026-I
