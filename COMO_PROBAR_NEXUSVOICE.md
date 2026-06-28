# 🎙️ Cómo probar NexusVoice + Cerebro IA

Guía rápida para probar las dos funciones nuevas de Nexus-DB:

1. **Cerebro IA** — convierte lenguaje natural (español) en SQL usando un modelo de IA (OpenAI o Claude), con el esquema real de tu base como contexto.
2. **Control por voz** — le hablas a la base, genera el SQL, lo ejecuta y te responde en voz alta. Con respaldo **offline** (sin internet).

---

## 0. Requisitos previos

- Windows con Python 3.10+ y un **micrófono**.
- Dependencias instaladas (las instala `run.bat` automáticamente, o manualmente):
  ```powershell
  .\.venv\Scripts\activate
  pip install -r src\requirements.txt
  ```

---

## 1. Configurar la clave de IA (para el cerebro)

El cerebro detecta automáticamente el proveedor según la clave que tengas:

- **OpenAI (ChatGPT):** variable `OPENAI_API_KEY`
- **Anthropic (Claude):** variable `ANTHROPIC_API_KEY`

> ⚠️ **Seguridad:** nunca compartas tu clave en chats, capturas ni en el código. Si se expuso, **revócala y genera una nueva** en el panel del proveedor.

En **PowerShell**:

```powershell
# Solo para la terminal actual:
$env:OPENAI_API_KEY = "TU_CLAVE_AQUI"

# Permanente (para todas las terminales futuras) — abre una terminal NUEVA después:
setx OPENAI_API_KEY "TU_CLAVE_AQUI"
```

Opcional — elegir el modelo (por defecto `gpt-4o-mini` / `claude-opus-4-8`):

```powershell
setx NEXUS_AI_MODEL "gpt-4o-mini"
```

> 💡 **Sin clave** la app **igual funciona**: el cerebro cae al traductor por patrones (reconoce frases simples como "muestra usuarios" o "cuántos clientes hay").

---

## 2. Iniciar la aplicación

Doble clic en `run.bat`, o desde una terminal:

```powershell
.\.venv\Scripts\python.exe src\main.py
```

Al abrir, elige el entorno:

```
Opción [1/2]: 1        ← Relacional (SQLite / PostgreSQL / MySQL)
```

Crea una base de prueba con datos:

```
connect sqlite prueba.db
create table clientes (id integer primary key, nombre text, ciudad text, total real)
insert into clientes (nombre, ciudad, total) values ('Ana', 'Lima', 1200)
insert into clientes (nombre, ciudad, total) values ('Beto', 'Tacna', 450)
insert into clientes (nombre, ciudad, total) values ('Carla', 'Lima', 980)
```

---

## 3. Probar el Cerebro IA (texto → SQL)

Usa el comando `ai "<frase>"`. Con clave configurada verás la etiqueta **🧠 IA**; sin clave, **🔤 patrón**.

```
ai "muéstrame los clientes de Lima ordenados por total de mayor a menor"
ai "cuál es el total promedio gastado por ciudad"
ai "dame el cliente que más gastó"
```

Te mostrará el SQL generado y preguntará `¿Ejecutar? (s/n)`. Pulsa `s` para ver el resultado.

✅ **Prueba clave para el jurado:** una frase que NO es un patrón fijo, como *"qué ciudad tiene más clientes registrados"*. El cerebro IA la resuelve; el traductor viejo no podía.

---

## 4. Probar el Control por Voz 🎙️

### a) Modo voz continuo (lo impresionante)

```
voice
```

Espera a ver `🎙️ Escuchando...` y di en voz alta, por ejemplo:

> *"muéstrame todos los clientes"*

Verás: la transcripción → el SQL generado → la tabla → y escucharás la respuesta hablada (voz "Sabina" en español).

Para terminar el modo voz: di **"salir"** (o pulsa `Ctrl+C`).

### b) Una sola orden por voz

```
voice once
```

### c) Sin micrófono (respaldo para la demo)

Si el micrófono falla en el auditorio, simula la voz escribiendo:

```
voice test muéstrame los clientes de Lima
```

Hace todo el flujo (IA + respuesta hablada) sin usar el micrófono.

---

## 5. Probar la voz OFFLINE (sin internet) 🔌

La transcripción usa Google (online) por defecto, con respaldo automático a **Vosk (offline)** si no hay internet. Para forzar el modo offline:

```
voice engine vosk     ← solo offline (no necesita internet)
voice                 ← ahora habla; se transcribe localmente
```

Volver al modo normal:

```
voice engine auto     ← online con respaldo offline (recomendado)
```

Ver el motor actual:

```
voice engine
```

> El modelo de voz en español ya está en `src/models/vosk-es/`. Si lo mueves, define la ruta con `setx NEXUS_VOSK_MODEL "C:\ruta\al\modelo"`.

---

## 6. Frases de ejemplo para la demostración

| Lo que dices / escribes | Lo que hace |
|---|---|
| "muéstrame todos los clientes" | `SELECT * FROM clientes` |
| "clientes de Lima ordenados por total de mayor a menor" | `... WHERE ciudad='Lima' ORDER BY total DESC` |
| "el total promedio gastado por ciudad" | `SELECT ciudad, AVG(total) ... GROUP BY ciudad` |
| "dame el cliente que más gastó" | `... ORDER BY total DESC LIMIT 1` |
| "cuántos clientes hay" | `SELECT COUNT(*) FROM clientes` |

---

## 7. Solución de problemas

| Síntoma | Causa / solución |
|---|---|
| Dice "🔤 patrón" en vez de "🧠 IA" | No detectó la clave. Verifica `OPENAI_API_KEY` y **abre una terminal nueva** tras `setx`. |
| "No pude generar SQL para esa petición" | La frase no encaja con el esquema; reformúlala o conéctate a una BD con tablas. |
| "Sin conexión con el servicio de transcripción" | No hay internet. Usa `voice engine vosk` para modo offline. |
| No se escucha la respuesta hablada | Revisa el volumen del sistema; la voz usa "Microsoft Sabina" (español). |
| No entiende el micrófono | Verifica el micrófono predeterminado de Windows; habla claro tras el aviso `🎙️ Escuchando...`. |
| Error al instalar `pyaudio` | `pip install pipwin && pipwin install pyaudio` (o usa una rueda precompilada). |

---

## Comandos útiles (resumen)

```
ai "<frase>"                  Lenguaje natural → SQL (con IA)
voice                         Modo voz continuo
voice once                    Una sola orden por voz
voice test <frase>            Probar sin micrófono
voice engine auto|google|vosk Cambiar motor de voz (vosk = offline)
help                          Ver todos los comandos
exit                          Salir
```
