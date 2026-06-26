

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

# Informe de Factibilidad

**Versión 1.0**

---

## CONTROL DE VERSIONES

| Versión | Hecha por | Revisada por | Aprobada por | Fecha | Motivo |
|---------|-----------|--------------|--------------|-------|--------|
| 1.0 | Jahuira Pilco, Dayan Elvis | Mamani Cori, Cristhian Carlos | Jahuira Pilco, Dayan Elvis | 26/04/2026 | Versión Original |

---

## ÍNDICE GENERAL

1. Descripción del Proyecto
2. Riesgos
3. Análisis de la Situación actual
4. Estudio de Factibilidad
5. Análisis Financiero
6. Conclusiones

---

## 1. Descripción del Proyecto

### 1.1. Nombre del proyecto

Administrador de BD en consola o terminal

### 1.2. Duración del proyecto

1 mes

### 1.3. Descripción

El presente proyecto tiene como finalidad el desarrollo de una aplicación de tipo CLI (Command Line Interface) orientada a la administración de bases de datos relacionales. El sistema permitirá a los usuarios interactuar con un gestor de base de datos como PostgreSQL, MySQL o SQLite, mediante comandos estructurados definidos por la aplicación.

La herramienta será capaz de procesar instrucciones ingresadas por el usuario, interpretarlas mediante un módulo de análisis sintáctico y ejecutarlas sobre la base de datos, permitiendo operaciones de definición y manipulación de datos (DDL y DML). Asimismo, el sistema proporcionará mecanismos básicos de validación, control de errores y visualización de resultados en formato legible dentro del entorno de consola.

Este proyecto se orienta tanto al aprendizaje práctico de la administración de bases de datos como al desarrollo de habilidades en el diseño de sistemas interactivos basados en comandos.

### 1.4. Objetivos

#### 1.4.1. Objetivo general

Desarrollar una aplicación en consola que permita administrar una base de datos mediante comandos, facilitando la ejecución de operaciones básicas de gestión de datos.

#### 1.4.2. Objetivos Específicos

- Implementar la conexión a una base de datos existente
- Desarrollar un sistema de comandos en consola (CLI)
- Permitir operaciones CRUD sobre las tablas
- Mostrar resultados de manera clara en consola
- Validar comandos y manejar errores básicos

---

## 2. Riesgos

- Falta de experiencia en conexión a bases de datos
- Problemas de configuración del entorno
- Errores en la interpretación de comandos
- Limitaciones de tiempo para completar todas las funcionalidades
- Fallas en la integración entre módulos

---

## 3. Análisis de la Situación actual

### 3.1. Planteamiento del problema

Las herramientas actuales de administración de bases de datos, en su mayoría, se presentan mediante interfaces gráficas que abstraen el funcionamiento interno de las operaciones, lo que limita la comprensión profunda de los procesos de manipulación de datos.

Por otro lado, en entornos profesionales y de servidores, el uso de interfaces de línea de comandos es predominante debido a su eficiencia, bajo consumo de recursos y capacidad de automatización. Sin embargo, dichas herramientas suelen presentar una curva de aprendizaje elevada.

En este contexto, se identifica la necesidad de desarrollar una solución que permita comprender y aplicar los conceptos de administración de bases de datos mediante una interfaz de consola simplificada y controlada.

### 3.2. Consideraciones de hardware y software

| Tipo de Recurso | Nombre | Descripción |
|-----------------|--------|-------------|
| Hardware | Computadora personal (PC o laptop) | Intel i5, RAM: 8 GB, HDD: 1 TB, Mouse y Teclado estándar. Equipo para desarrollar y probar el sistema. |
| Software | Windows 10/11 | Sistema Operativo base para ejecutar herramientas de desarrollo y el sistema. |
| Software | Python 3.8+ | Ampliamente utilizado en aplicaciones CLI; sintaxis clara; gran cantidad de bibliotecas |
| Software | VS Code | Entorno de desarrollo gratuito con soporte para Python |

---

## 4. Estudio de Factibilidad

### 4.1. Factibilidad Técnica

| Cantidad | Recurso | Descripción |
|----------|---------|-------------|
| 1 | Laptop | Laptop ASUS, Procesador Ryzen, RAM: 16 GB, SSD: 1 TB y Mouse |
| 1 | Laptop | Laptop Lenovo, Procesador Intel Core i5 de 6ta generación, 8 GB de RAM, SSD de 500 GB y Mouse |

**Conclusión Técnica:** El proyecto es técnicamente viable. Se cuenta con dos equipos con especificaciones adecuadas para el desarrollo. Python es un lenguaje ideal para aplicaciones CLI y no requiere hardware especializado. Las librerías necesarias para la conexión a bases de datos son de código abierto y están disponibles gratuitamente.

---

### 4.2. Factibilidad Económica

#### 4.2.1. Costos Generales

| Item | Cantidad | Costo Unitario S/. | Costo Total S/. |
|------|----------|-------------------|-----------------|
| Laptop para desarrollo | 2 | 2500 | 5000 |
| Material de escritorio | 1 | 40 | 40 |
| **Total** | | | **5040** |

#### 4.2.2. Costos operativos durante el desarrollo

| Concepto | Costo Mensual S/. | Duración meses | Costo Total S/. |
|----------|-------------------|----------------|-----------------|
| Energía eléctrica | 80 | 1 | 80 |
| Internet | 100 | 1 | 100 |
| **Total** | | | **180** |

#### 4.2.3. Costos del ambiente

| Recurso | Costo Unitario S/. | Cantidad | Costo Total S/. |
|---------|-------------------|----------|-----------------|
| Configuración de entorno de desarrollo | 50 | 1 | 50 |
| Pruebas del sistema | 80 | 1 | 80 |
| Repositorio GitHub | 20 | 1 | 20 |
| **Total** | | | **150** |

#### 4.2.4. Costos de personal

| Rol | Cantidad | Sueldo Mensual S/. | Meses | Subtotal S/. |
|-----|----------|-------------------|-------|--------------|
| Analista y Desarrollador | 2 | 3000 | 1 | 6000 |
| **Total** | | | | **6000** |

#### 4.2.5. Costos totales del desarrollo del sistema

| Categoría | Total S/. |
|-----------|-----------|
| Costos Generales | 5,040 |
| Costos Operativos | 180 |
| Costos del Ambiente | 150 |
| Costos de Personal | 6,000 |
| **TOTAL GENERAL** | **11,370** |

---

### 4.3. Factibilidad Operativa

| Aspecto | Descripción | Estado |
|---------|-------------|-------|
| Usuarios | Estudiantes de cursos de bases de datos, docentes y desarrolladores que requieran administrar bases de datos desde consola | Viable |
| Curva de aprendizaje | Baja gracias al comando help y sintaxis intuitiva | Viable |
| Mantenimiento | El código es simple y modular, fácil de mantener | Viable |
| Documentación | Se incluirá un manual básico dentro del repositorio | Viable |
| Soporte | Durante el periodo académico, los desarrolladores brindarán soporte | Viable |

De acuerdo con el análisis presentado en la tabla, la factibilidad operativa del sistema resulta totalmente viable. Los usuarios objetivo tienen el perfil adecuado (conocimiento básico de bases de datos), el sistema incluye un comando de ayuda para facilitar su uso, y los riesgos identificados son controlables mediante una adecuada implementación de manejo de errores y documentación.

---

### 4.4. Factibilidad Legal

| Aspecto Legal | Descripción | Cumplimiento |
|---------------|-------------|--------------|
| Protección de Datos Personales | El sistema no almacena ni procesa datos personales de los usuarios. Solo interactúa con bases de datos locales del usuario. | Sí |
| Uso de Software | Python es software de código abierto con licencia PSF. Visual Studio Code es gratuito. No se requiere software comercial. | Sí |
| Propiedad Intelectual | El código desarrollado es propiedad de los autores. Se utilizará licencia MIT para permitir uso académico y comercial. | Sí |

---

### 4.5. Factibilidad Social

| Aspecto | Descripción | Impacto |
|---------|-------------|---------|
| Estudiantes | Permite comprender el funcionamiento interno de bases de datos sin depender de interfaces gráficas | Positivo |
| Docentes | Herramienta didáctica para enseñar SQL y administración de bases de datos | Positivo |
| Desarrolladores | Facilita el aprendizaje de conexiones a bases de datos mediante Python | Positivo |

---

### 4.6. Factibilidad Ambiental

| Aspecto | Descripción | Impacto |
|---------|-------------|---------|
| Uso de papel | No requiere documentación física ni reportes impresos | Positivo |
| Consumo energético | Funciona en equipos de bajo consumo, sin requerir hardware adicional | Positivo |
| Residuos electrónicos | Al ser software puro, no genera residuos físicos | Positivo |

---

## 5. Análisis Financiero

### 5.1. Justificación de la Inversión

La inversión en el desarrollo del Administrador de BD en consola se justifica por los siguientes motivos:

- Eliminación de dependencia de herramientas gráficas comerciales como DBeaver Pro o Navicat
- Reducción del tiempo de aprendizaje para comandos SQL mediante una interfaz simplificada
- Automatización de tareas repetitivas de administración de bases de datos
- Disponibilidad de una herramienta didáctica gratuita para la enseñanza de bases de datos
- Bajos costos en infraestructura por ser una aplicación 100% Python

### 5.2. Beneficios del Proyecto

**Beneficios Intangibles**

- Fortalecimiento de competencias técnicas en el equipo desarrollador
- Contribución al aprendizaje práctico de bases de datos
- Disponibilidad de código fuente para futuras adaptaciones
- Independencia de plataformas comerciales
- Código ligero y portable al usar solo Python estándar

### 5.3. Criterios de Inversión

Para la evaluación financiera se considera un horizonte de 3 años, con un costo de oportunidad de capital COK del 12 por ciento anual.

**Proyección de beneficios anuales**

| Año | Beneficios S/. | Mantenimiento S/. | Beneficio Neto S/. |
|-----|----------------|-------------------|-------------------|
| 0 | 0 | 11,370 | -11,370 |
| 1 | 4,500 | 400 | 4,100 |
| 2 | 5,000 | 450 | 4,550 |
| 3 | 5,500 | 500 | 5,000 |

#### 5.3.1. Relación Beneficio Costo B/C

Valor Presente de los Beneficios VPB = 10,847.15

Valor Presente de los Costos VPC = 12,441.80

**Relación B/C = 10,847.15 / 12,441.80 = 0.87**

**Interpretación:** B/C es menor a 1, por lo tanto, los beneficios no superan a los costos.

#### 5.3.2. Valor Actual Neto VAN

VAN = -11,370 + 4,100/(1.12)¹ + 4,550/(1.12)² + 5,000/(1.12)³

VAN = -11,370 + 3,660.89 + 3,627.26 + 3,559.00

**VAN = S/. -522.85**

**Interpretación:** VAN es menor a 0, por lo tanto, el proyecto no genera valor suficiente para recuperar la inversión.

#### 5.3.3. Tasa Interna de Retorno TIR

**TIR ≈ 9.4 por ciento**

**Interpretación:** TIR 9.4% es menor al COK 12%, por lo tanto, el proyecto no es rentable.

---

**Resumen de Criterios de Inversión**

| Indicador | Valor | Criterio | Decisión |
|-----------|-------|----------|----------|
| Relación B/C | 0.87 | Mayor a 1 | Rechazar |
| VAN | S/. -522.85 | Mayor a 0 | Rechazar |
| TIR | 9.4% | Mayor a COK 12% | Rechazar |

---

## 6. Conclusiones

El análisis de factibilidad realizado para el proyecto Administrador de BD en consola o terminal arroja los siguientes resultados:

**Factibilidad Técnica:** El proyecto es viable pues se cuenta con los conocimientos y herramientas necesarias para su desarrollo. Python con sus librerías estándar permite construir una aplicación CLI completa sin requerir infraestructura adicional.

**Factibilidad Económica:** La inversión total asciende a S/. 11,370.00. Los indicadores financieros muestran resultados no favorables con un VAN de S/. -522.85, una TIR de 9.4 por ciento y una relación Beneficio Costo de 0.87, todos inferiores a los criterios mínimos establecidos.

**Factibilidad Operativa:** La interfaz de línea de comandos con comando help facilita la curva de aprendizaje. Los usuarios objetivo estudiantes y docentes cuentan con el perfil adecuado.

**Factibilidad Legal:** El proyecto utiliza exclusivamente software de código abierto con licencias permisivas, cumpliendo con las normativas de propiedad intelectual.

**Factibilidad Social:** El impacto es positivo al contribuir con la formación de los estudiantes y ofrecer una herramienta didáctica para la enseñanza de bases de datos.

**Factibilidad Ambiental:** El proyecto no genera residuos electrónicos ni consume recursos adicionales, promoviendo el uso de software libre.

**Conclusión Final:** A pesar de que el proyecto es técnicamente viable y presenta beneficios sociales y educativos significativos, desde la perspectiva estrictamente financiera los indicadores muestran que no se recuperaría la inversión. Sin embargo, tratándose de un proyecto académico donde los costos de personal no representan un desembolso real y los equipos ya son propiedad de los desarrolladores, se recomienda proceder con el desarrollo considerando el valor formativo y la contribución al aprendizaje.
