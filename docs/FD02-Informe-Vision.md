![./media/media/image1.png](./media/logo-upt.png)

# UNIVERSIDAD PRIVADA DE TACNA

# FACULTAD DE INGENIERÍA

# Escuela Profesional de Ingeniería de Sistemas

## Proyecto Administrador de BD en consola o terminal

**Curso:** Base de Datos II

**Docente:** Patrick Cuadros Quiroga

**Integrantes:**

Jahuira Pilco, Dayan Elvis (2022075749)  
Mamani Cori, Cristhian Carlos (2023077282)

---

**Tacna – Perú**  
**2026**

---

# Sistema Administrador de BD en consola o terminal

# Documento de Visión

**Versión 2.0**

---

## CONTROL DE VERSIONES

| Versión | Hecha por | Revisada por | Aprobada por | Fecha | Motivo |
|---------|-----------|--------------|--------------|-------|--------|
| 1.0 | Jahuira Pilco, Dayan Elvis | Mamani Cori, Cristhian Carlos | Jahuira Pilco, Dayan Elvis | 04/04/2026 | Versión Original |

---

## ÍNDICE GENERAL

1. Introducción  
2. Posicionamiento  
3. Descripción de interesados y usuarios  
4. Vista General del Producto  
5. Características del producto  
6. Restricciones  
7. Rangos de calidad  
8. Precedencia y Prioridad  
9. Otros requerimientos del producto  
10. Conclusiones  
11. Recomendaciones  
12. Bibliografía  
13. Webgrafía  

---

## 1. Introducción

### 1.1 Propósito

Definir la visión general del sistema “Administrador de Base de Datos en Consola”, estableciendo objetivos, alcance, características y actores involucrados.

### 1.2 Alcance

El sistema permitirá administrar bases de datos mediante CLI ejecutando operaciones SQL.

**Dentro del alcance:**

- Conexión a BD existentes  
- Ejecución de SQL (SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER)  
- Visualización en tabla  
- Listado de tablas  
- Manejo básico de errores  
- Comando `help` y `exit`  

**Fuera del alcance:**

- Motor de BD propio  
- Interfaz gráfica  
- Gestión de usuarios  
- Exportación (CSV, Excel, PDF)  
- Conexión múltiple simultánea  
- Backups automatizados  

---

### 1.3 Definiciones

| Término | Definición |
|--------|-----------|
| BD | Base de datos |
| CLI | Command Line Interface |
| CRUD | Create, Read, Update, Delete |
| DBMS | Sistema gestor de BD |
| SQL | Structured Query Language |
| DDL | Data Definition Language |
| DML | Data Manipulation Language |

---

### 1.4 Referencias

- Documentación Python  
- PostgreSQL  
- MySQL  
- SQLite  
- Informe FD01  

---

### 1.5 Visión General

Desarrollar una herramienta CLI que permita interactuar con bases de datos de forma directa, reforzando el aprendizaje de SQL sin depender de interfaces gráficas.

---

## 2. Posicionamiento

### 2.1 Oportunidad de negocio

Existe necesidad educativa de herramientas CLI simplificadas para entender BD sin abstracciones gráficas.

### 2.2 Problema

Las herramientas actuales:

- Ocultan procesos internos  
- Son complejas en CLI para principiantes  

---

## 3. Interesados y Usuarios

### 3.1 Interesados

| Interesado | Rol | Expectativa |
|-----------|-----|------------|
| Docente | Supervisor | Cumplimiento técnico |
| Estudiantes dev | Desarrollo | Aprendizaje |
| Estudiantes usuarios | Uso | Facilidad |
| Universidad | Institución | Calidad académica |

---

### 3.2 Usuarios

| Usuario | Descripción | Frecuencia |
|--------|-------------|-----------|
| Básico | SQL básico | 1-2 veces/semana |
| Intermedio | Consultas complejas | Varias veces |
| Técnico | Admin BD | Diario |

---

### 3.3 Entorno

Uso en terminal (Windows, Linux, macOS).

---

### 3.4 Perfiles interesados

| Perfil | Responsabilidad |
|-------|----------------|
| Docente | Evaluar |
| Estudiante | Desarrollar |

---

### 3.5 Perfiles usuarios

| Perfil | Conocimiento | Uso |
|-------|--------------|-----|
| Básico | SQL simple | help |
| Intermedio | SQL avanzado | consultas |
| Técnico | Admin BD | uso total |

---

### 3.6 Necesidades

| Necesidad | Prioridad |
|----------|----------|
| Acceso simple CLI | Alta |
| Aprender SQL | Alta |
| Ligero | Media |
| Feedback claro | Media |
| Documentación | Alta |

---

## 4. Vista General

### 4.1 Perspectiva

Aplicación Python que actúa como intermediario entre usuario y DBMS.

---

### 4.2 Capacidades

- Conexión BD  
- SQL  
- CRUD  
- Tablas  
- Resultados  

---

### 4.3 Suposiciones

- BD instalada  
- Librerías disponibles  

---

### 4.4 Costos

| Categoría | Total S/. |
|----------|-----------|
| Generales | 5040 |
| Operativos | 180 |
| Ambiente | 150 |
| Personal | 6000 |
| **Total** | **11370** |

---

### 4.5 Licencia

Licencia MIT.

---

## 5. Características

**MUST**

- Conexión BD  
- SQL  
- Tablas  
- help / exit  
- Manejo errores  

**SHOULD**

- tables  
- info  
- disconnect  
- clear  

**COULD**

- help avanzado  
- historial  
- exportación CSV  

---

## 6. Restricciones

- Conocimiento SQL  
- BD instalada  
- Sin GUI  
- Dependencias Python  
- Tiempo 1 mes  

---

## 7. Calidad

- Usabilidad < 2 min  
- Fallos < 1%  
- Respuesta < 1s  
- Multiplataforma  

---

## 8. Prioridad

1. REPL  
2. SQLite  
3. SQL  
4. Tabla  
5. PostgreSQL  
6. MySQL  

---

## 9. Otros requerimientos

### Legales

- Licencia MIT  
- Código propio  

### Comunicación

- Mensajes claros  
- Tablas ASCII  

### Plataforma

- Windows/Linux/macOS  
- Python 3.8+  

### Calidad y Seguridad

- Código modular  
- No guardar credenciales  

---

## 10. Conclusiones

El sistema es viable, educativo y funcional para administración de BD mediante CLI.

---

## 11. Recomendaciones

- Probar con los 3 motores  
- Preparar demo  
- Verificar terminal  
- Documentar README  

---

## 12. Bibliografía

- Ramakrishnan  
- Silberschatz  
- Beaulieu  
- Python Docs  

---

## 13. Webgrafía

- https://docs.python.org  
- https://postgresql.org  
- https://dev.mysql.com  
- https://sqlite.org  
