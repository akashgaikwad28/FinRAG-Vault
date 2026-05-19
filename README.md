# FinRAG Vault – Enterprise AI Financial Document Management System

FinRAG Vault is a production-grade, asynchronous FastAPI financial document management system utilizing high-performance Retrieval-Augmented Generation (RAG). It implements strict Role-Based Access Control (RBAC), multi-tenant enterprise isolation boundaries, structured correlation logging, and a hybrid vector search pipeline utilizing **sentence-transformers** embeddings and **Cross-Encoder reranking**.

---

## 🏛️ System Architecture

```mermaid
flowchart TD
    subgraph Clients ["Client Applications"]
        UI["Web Portal / Swagger UI"]
    end

    subgraph API ["FastAPI Service Layer"]
        CORS["CORS Middleware"] --> RL["Rate Limiting Middleware"]
        RL --> AM["Auth Correlation Middleware"]
        AM --> LM["Structured Logging Middleware"]
        LM --> Router["API Routing Controllers"]
    end

    subgraph Auth ["Authentication & RBAC"]
        JWT["JWT Security Guards"]
        RBAC["Granular Permissions Matrix"]
    end

    subgraph DB ["Data Persistence Engines"]
        PG["PostgreSQL (Relational Metadata)"]
        QD["Qdrant (Vector Embeddings Space)"]
    end

    subgraph Ingestion ["Asynchronous Processing Ingestion"]
        Parser["ParserService (PDF, DOCX, TXT)"]
        Chunker["LangChain ChunkingService (Recursive Splitter)"]
        Embedder["Sentence-Transformers MiniLM (384-dim)"]
        Reranker["Cross-Encoder ms-marco (MiniLM-L-6-v2)"]
    end

    Router -.-> JWT
    Router -.-> RBAC
    Router === PG
    Router -.-> Parser
    Parser --> Chunker
    Chunker --> Embedder
    Embedder === QD
    
    %% Retrieval / Search Flow
    Router ==> VectorSearch["Vector Semantic Match"]
    VectorSearch ==> QD
    VectorSearch ==> Enrichment["Relational Verification (RagRepository)"]
    Enrichment ==> PG
    Enrichment ==> Reranking["Cross-Encoder Reranker"]
    Reranking ==> Deduplication["Diversity Deduplication (Top 5)"]
```

---

## 🔒 Key Enterprise Implementation Enhancements

### 1. Multi-Tenant Enterprise Isolation Boundaries
FinRAG Vault implements strict multi-tenant boundary security. 
- Every standard **Client** is permanently isolated within their assigned `company_name`.
- When retrieving lists of documents or executing RAG semantic searches, client query parameters are **transparently overridden** at the controller route layer to inject the client's `company_name` filter.
- Detail lookups by UUID strictly verify matching company parameters, preventing ID-guessing or enumeration attacks completely.

### 2. UUID Primary Key Architecture
In compliance with enterprise-grade standards, the system rejects incremental integer primary keys:
- Every table (`users`, `roles`, `documents`, `audit_logs`) uses cryptographically secure **UUIDv4** keys.
- Auto-increment sequences are completely removed, preventing key enumeration vulnerabilities.

### 3. Non-Blocking Background RAG Indexing
To prevent file uploads from blocking main HTTP connection threads:
- Stream writes are written in **64KB chunks** to disk using `aiofiles` preventing RAM spikes.
- Metadata is inserted into PostgreSQL with status `processing`.
- High-latency GPU/CPU-intensive tasks (parsing, chunking, embedding generation, Qdrant upserts) are delegated to FastAPI **BackgroundTasks**.
- Background runners spawn an isolated database session block to avoid session leaks, automatically updating statuses to `indexed` or `failed` (carrying error details) upon completion.

### 4. Advanced Hybrid Search & Diversity Deduplication
Our RAG retrieval pipeline implements:
1. **Semantic Vector Search**: Generates a 384-dimensional query vector and extracts the top 20 candidate chunks from Qdrant matching corporate filters.
2. **Relational Synchronization (RagRepository)**: Validates that candidate vectors retrieved from Qdrant still exist and are fully marked as `indexed` in PostgreSQL, preventing vector drift from soft-deleted documents.
3. **Cross-Encoder Reranking**: Uses `cross-encoder/ms-marco-MiniLM-L-6-v2` in a CPU-safe thread executor to assign precise relevance scores.
4. **Diversity Deduplication**: Sorts candidates and filters consecutive segments, restricting candidates to at most **2 chunks per document** before returning the top 5 high-precision passages. This guarantees broader context coverage for QA models.

---

## 🛠️ API Router Endpoint Summary

| Category | Method | Endpoint | Clearance Guard | Summary / Description |
| :--- | :---: | :--- | :---: | :--- |
| **Auth** | `POST` | `/api/v1/auth/register` | Open | Register a new Client account |
| **Auth** | `POST` | `/api/v1/auth/login` | Open | Authenticate and retrieve JWT bearer token |
| **Auth** | `POST` | `/api/v1/auth/token` | Open | OAuth2 compliant Form token endpoint (Swagger lock) |
| **Users** | `GET` | `/api/v1/users/me` | Authenticated | Get currently authenticated profile details |
| **Users** | `GET` | `/api/v1/users` | `user:manage` | Paginated, filtered list of users (Admin only) |
| **Users** | `PUT` | `/api/v1/users/{id}` | `user:manage` | Modify user attributes and assigned role groups |
| **Users** | `DELETE` | `/api/v1/users/{id}` | `user:manage` | Soft-delete a user record |
| **Roles** | `GET` | `/api/v1/roles` | `role:manage` | List all defined role permission definitions |
| **Roles** | `POST` | `/api/v1/roles` | `role:manage` | Provision a new custom Role group |
| **Docs** | `POST` | `/api/v1/documents/upload` | `document:upload` | Stream, parse, and queue indexing for file |
| **Docs** | `GET` | `/api/v1/documents` | `document:read` | Paginated listing (Company isolated for Client) |
| **Docs** | `GET` | `/api/v1/documents/{id}` | `document:read` | Fetch document details (Company isolated) |
| **Docs** | `DELETE` | `/api/v1/documents/{id}` | `document:delete` | Soft-delete metadata and remove Qdrant points |
| **RAG** | `POST` | `/api/v1/rag/search` | `rag:search` | Perform hybrid vector search (Company isolated) |
| **RAG** | `GET` | `/api/v1/rag/context/{id}`| `document:read` | Retrieve raw sorted chunks for a document ID |
| **Health** | `GET` | `/api/v1/health` | Open | Liveness and readiness checks |

---

## ⚡ Complete Setup & Running Guide

### Option 1: Running with Docker Containers (Recommended & Production-Grade)
Docker Compose automatically manages building the FastAPI image, setting up network boundaries, provisioning persistent database volumes, and waiting for relational/vector engines to be healthy.

#### 1. Spin up the entire multi-service stack:
Run this command from the root directory (`C:\Users\akash\FinRAG Vault`):
```bash
docker-compose up --build -d
```
*   `--build` compiles the multi-stage Dockerfile and caches wheels.
*   `-d` runs the entire stack in the background (detached mode).

#### 2. View server console logs:
To monitor system startups, database seed processes, or trace requests live:
```bash
docker-compose logs -f web
```

#### 3. Default Seeded Accounts:
During startup, the system automatically seeds standard security roles and a default system administrator account:
*   **Admin Email**: `admin@finragvault.com`
*   **Admin Password**: `AdminPassword123!`

#### 4. Stop and tear down the containers:
To stop execution and preserve your documents, databases, and vectors:
```bash
docker-compose down
```
To stop the application and completely wipe all persistent database volumes, vectors, and uploaded documents:
```bash
docker-compose down -v
```

---

### Option 2: Running Locally (For Native Local Development)
If you want to run the FastAPI app directly on your local workstation outside of Docker:

#### 1. Configure the local `.env` overrides:
Ensure you have a local PostgreSQL instance and Qdrant container running on your machine, then open your [`.env`](file:///c:/Users/akash/FinRAG%20Vault/.env) and uncomment the local `localhost` target lines:
```ini
# Edit your local .env:
DATABASE_URL=postgresql+asyncpg://postgres:SecretPassword123!@localhost:5432/finrag_vault
QDRANT_HOST=localhost
```

#### 2. Setup and activate a Python virtual environment:
```bash
python -m venv venv
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On Windows Command Prompt:
.\venv\Scripts\activate.bat
```

#### 3. Install required system packages:
```bash
pip install -r requirements.txt
```

#### 4. Start the FastAPI development server:
To avoid Python pathing issues (like `ModuleNotFoundError: No module named 'app'`), launch the application from the root directory using **Uvicorn**:
```bash
uvicorn app.main:app --reload
```
*   `--reload` enables live-reload, monitoring your code changes and automatically hot-reloading the dev server.

---

### Option 3: Deploying to the Cloud (Render Deployment)
FinRAG Vault is fully pre-configured for automated cloud deployment using **Render Blueprints**. 

#### How to Deploy:
1. **Push your code to GitHub**:
   Create a new repository on your GitHub account and push the entire codebase to it.
2. **Launch on Render**:
   - Navigate to the [Render Dashboard](https://dashboard.render.com/).
   - Click the **New +** button in the top-right and select **Blueprint**.
   - Connect your GitHub repository.
3. **Automatic Provisioning**:
   Render will parse our [`render.yaml`](file:///c:/Users/akash/FinRAG%20Vault/render.yaml) specification and automatically set up:
   *   A managed **PostgreSQL** database instance.
   *   A secure private **Qdrant** database service (using a 10GB persistent storage disk to ensure no vector loss on server restarts).
   *   Our FastAPI **Web Service** (compiled from our multi-stage production `Dockerfile`, backed by a 10GB persistent storage disk to secure uploaded PDFs/docs).
   *   An automatically generated cryptographically secure JWT `SECRET_KEY` environment variable.
4. **Boot & Execution**:
   Render handles the entire container build, automatically executes schemas, seeds initial roles/admin accounts during the startup lifespan, and exposes a secure public HTTPS gateway for your API endpoints.

---

## 🧪 Running Unit Tests
FinRAG Vault includes a hermetic, zero-dependency unit test suite using an in-memory SQLite database (`aiosqlite`) and mocks for Qdrant.

To run the test suite:
1. Activate your virtual environment and install testing dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run `pytest` from the root directory:
   ```bash
   pytest -v
   ```
