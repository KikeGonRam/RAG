# 🧠 RAG Ollama API

Sistema RAG (Retrieval Augmented Generation) local con **FastAPI + ChromaDB + Ollama**.  
100% local, sin OpenAI ni APIs externas.

```
Usuario → POST /ask → Embedding → ChromaDB → Contexto → Ollama → Respuesta
```

---

## 📁 Estructura del proyecto

```
rag-ollama/
├── app/
│   ├── main.py          # FastAPI entrypoint + endpoints
│   ├── rag.py           # Orquestador del pipeline RAG
│   ├── vectorstore.py   # ChromaDB wrapper
│   ├── llm.py           # Cliente Ollama (chat + streaming)
│   ├── embeddings.py    # Cliente embeddings Ollama
│   ├── utils.py         # Chunking de texto
│   └── config.py        # Configuración via .env
├── data/
│   └── chroma_db/       # Persistencia local de vectores
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🚀 Inicio rápido con Docker

### 1. Clonar y configurar

```bash
git clone <repo>
cd rag-ollama
cp .env.example .env
```

### 2. Levantar todos los servicios

```bash
docker compose up -d
```

Esto levanta:
- **Ollama** en `localhost:11434`
- **ollama-setup**: descarga automáticamente `qwen2.5:7b` y `nomic-embed-text`
- **API FastAPI** en `localhost:8000`

> ⚠️ La primera vez puede tardar varios minutos mientras se descargan los modelos (~5 GB).

### 3. Verificar que todo está corriendo

```bash
# Logs en tiempo real
docker compose logs -f

# Health check
curl http://localhost:8000/health
```

---

## 📡 Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/` | Info del servidor |
| `GET` | `/health` | Estado de Ollama y ChromaDB |
| `GET` | `/ui` | Interfaz visual para colaboradores |
| `GET` | `/admin` | Panel visual para generar y registrar API keys |
| `GET` | `/docs` | Swagger UI interactivo |
| `POST` | `/ingest` | Ingesta documentos |
| `POST` | `/ask` | Pregunta al sistema RAG |
| `GET` | `/chats` | Lista chats del colaborador |
| `POST` | `/chats` | Crea un chat nuevo |
| `GET` | `/chats/{id}/messages` | Historial del chat |
| `DELETE` | `/chats/{id}` | Elimina un chat |
| `GET` | `/admin/keys` | Lista keys registradas (admin) |
| `POST` | `/admin/keys` | Genera y registra key (admin) |
| `DELETE` | `/admin/keys/{id}` | Desactiva key (admin) |
| `GET` | `/collections` | Lista colecciones |
| `DELETE` | `/collection/{name}` | Elimina una colección |

---

## 🧪 Ejemplos de uso

### Ingestar un texto

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "text": "FastAPI es un framework web moderno para Python basado en Starlette y Pydantic. Permite crear APIs REST con validación automática, documentación interactiva y soporte para async/await.",
    "collection": "default"
  }'
```

### Ingestar múltiples documentos

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [
      "ChromaDB es una base de datos vectorial open-source diseñada para aplicaciones de IA.",
      "Los embeddings son representaciones numéricas de texto que capturan su significado semántico.",
      "RAG combina búsqueda de información con generación de texto para respuestas más precisas."
    ],
    "collection": "default"
  }'
```

### Hacer una pregunta

```bash
curl -X POST http://localhost:8000/ask \
  -H "X-API-Key: TU_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "¿Qué es FastAPI y para qué sirve?",
    "collection": "default",
    "top_k": 3
  }'
```

### Pregunta con streaming

```bash
curl -X POST http://localhost:8000/ask \
  -H "X-API-Key: TU_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Explica qué es un embedding",
    "stream": true
  }'
```

### Ver colecciones

```bash
curl http://localhost:8000/collections \
  -H "X-API-Key: TU_API_KEY"
```

### Eliminar colección

```bash
curl -X DELETE http://localhost:8000/collection/default \
  -H "X-API-Key: TU_API_KEY"
```

---

## ⚙️ Configuración

Variables de entorno disponibles en `.env`:

| Variable | Default | Descripción |
| --------- | ------- | ----------- |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | URL de Ollama |
| `OLLAMA_MODEL` | `qwen2.5:7b` | Modelo LLM |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Modelo de embeddings |
| `CHROMA_PATH` | `/app/data/chroma_db` | Ruta de persistencia |
| `CHUNK_SIZE` | `512` | Tamaño de chunk (chars) |
| `CHUNK_OVERLAP` | `64` | Overlap entre chunks (chars) |
| `LLM_TEMPERATURE` | `0.2` | Temperatura del LLM |
| `LLM_CTX_WINDOW` | `4096` | Ventana de contexto |
| `API_KEY_ENABLED` | `false` | Activa validación de API keys |
| `API_KEYS` | `` | Lista estática opcional de keys separadas por coma |
| `API_KEY_HEADER_NAME` | `X-API-Key` | Nombre del header HTTP |
| `ADMIN_PANEL_PASSWORD` | `` | Password del panel admin de keys |
| `ADMIN_PASSWORD_HEADER_NAME` | `X-Admin-Password` | Header para endpoints admin |

### Acceso para colaboradores con API keys

Si quieres compartir la API con colaboradores, activa API keys en `.env` y administra keys desde el panel.

1. Configura `.env`:

```env
API_KEY_ENABLED=true
API_KEY_HEADER_NAME=X-API-Key
ADMIN_PANEL_PASSWORD=TU_PASSWORD_ADMIN_SEGURA
ADMIN_PASSWORD_HEADER_NAME=X-Admin-Password
```

1. Reinicia la API:

```bash
docker compose up -d --build api
```

1. Abre el panel admin:

```text
http://localhost:8000/admin
```

1. Genera una key por colaborador desde el panel.

Opcionalmente puedes generar keys por terminal:

```bash
# Linux/macOS/Git Bash
openssl rand -hex 32

# PowerShell
[guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
```

Tambien puedes generarlas en lote con Python:

```bash
python -m app.generate_api_keys --count 5
```

Endpoints protegidos por key:

- `POST /ask`
- `POST /ingest`
- `GET /collections`
- `DELETE /collection/{name}`

`/` y `/health` quedan públicos para monitoreo.

### Panel de administrador de keys

Con `ADMIN_PANEL_PASSWORD` configurado, puedes administrar keys desde:

```text
http://localhost:8000/admin
```

Funciones del panel:

- Generar key nueva por colaborador
- Ver registro de keys activas/inactivas
- Revisar `use_count` y `last_used_at`
- Desactivar keys comprometidas o vencidas

---

## 🛠️ Desarrollo sin Docker

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate   # Linux/Mac
# venv\Scripts\activate   # Windows

# Instalar dependencias
pip install -r requirements.txt

# Ollama debe estar corriendo localmente
# Cambiar OLLAMA_BASE_URL en .env a http://127.0.0.1:11434

# Iniciar API
uvicorn app.main:app --reload
```

---

## 🐳 Comandos Docker útiles

```bash
# Levantar servicios
docker compose up -d

# Ver logs
docker compose logs -f api
docker compose logs -f ollama

# Detener
docker compose down

# Detener y borrar volúmenes (⚠️ borra los modelos y datos)
docker compose down -v

# Reconstruir imagen de la API
docker compose build api

# Entrar al contenedor de la API
docker exec -it rag-api bash

# Ver modelos descargados en Ollama
docker exec -it rag-ollama ollama list
```

---

## 🏗️ Arquitectura RAG

```text
┌─────────────┐     POST /ingest      ┌──────────────┐
│   Cliente   │ ──────────────────>   │   FastAPI    │
│  (curl/JS)  │                       │   main.py    │
└─────────────┘                       └──────┬───────┘
                                             │
                              ┌──────────────▼───────────────┐
                              │         RAGPipeline          │
                              │           rag.py             │
                              └──┬───────────┬──────────────┘
                                 │           │
                    ┌────────────▼──┐   ┌────▼──────────┐
                    │  EmbeddingClient  │   VectorStore  │
                    │  embeddings.py │   │ vectorstore.py │
                    └────────────┬──┘   └────┬───────────┘
                                 │           │
                    ┌────────────▼──┐   ┌────▼───────────┐
                    │    Ollama     │   │   ChromaDB     │
                    │ (embeddings)  │   │  (persistente) │
                    └───────────────┘   └────────────────┘

POST /ask:
  pregunta → embed → query ChromaDB → top-k chunks
  → build prompt → Ollama /api/chat → respuesta
```

---

## 📦 Tecnologías

- **FastAPI** — Framework web async
- **ChromaDB** — Base de datos vectorial local
- **Ollama** — LLM local (qwen2.5:7b)
- **nomic-embed-text** — Modelo de embeddings
- **httpx** — Cliente HTTP async
- **Docker Compose** — Orquestación de servicios

---

## 🔮 Próximos pasos sugeridos

- [ ] Frontend tipo ChatGPT con React/Next.js
- [ ] Soporte para ingesta de PDFs
- [ ] Multi-tenancy por colecciones separadas
- [ ] Autenticación con JWT
- [ ] Rate limiting
- [ ] Métricas con Prometheus + Grafana
