# Monytix Architecture Overview

## Five-Layer Architecture

Monytix follows a five-layer architecture pattern ensuring clean separation of concerns and scalable design.

---

## Layer 1: Input Layer

**Purpose**: Capture transaction data from multiple sources

### Components

- Manual Entry API
- Email Parser
- File Upload (PDF/CSV)

### Files

- `app/routers/transactions.py` - Manual entry
- `app/routers/uploads.py` - File uploads
- `app/workers/gmail_worker.py` - Email parsing

### Data Flow

```.
User Input → Validation → MongoDB (raw) → Queue Processing
```

---

## Layer 2: Categorization Engine

**Purpose**: Rule-based transaction categorization

### Componentss

- Keyword matching
- Regex pattern matching
- Confidence scoring
- Transaction type detection

### Filess

- `app/services/categorization_engine.py` - Core engine
- `app/workers/ml_worker.py` - Batch processing
- `app/models/postgresql_models.py` - Category model

### Data Flows

```d
Raw Transaction → Rule Matching → Category + Confidence → PostgreSQL
```

---

## Layer 3: Analytics Layer

**Purpose**: Aggregate and calculate statistics

### Componentsss

- Spend aggregation
- Category breakdown
- Leak detection
- Trend analysis

### Filesss

- `app/routers/transactions.py` - Stats endpoints
- `app/routers/ml.py` - Analytics endpoints
- `app/services/analytics.py` - Calculation logic

### Data Flowss

```d
PostgreSQL → Aggregation → Cache (Redis) → API Response
```

---

## Layer 4: UI Layer

**Purpose**: Visualize and interact with data

### Componentssss

- Monytix Console (Dashboard)
- SpendSense (Analytics)
- BudgetRack (Budgets)
- MoneyMoments (Timeline)

### Filesa

- `src/pages/Console.tsx`
- `src/pages/SpendSense.tsx`
- `src/pages/BudgetRack.tsx`
- `src/pages/MoneyMoments.tsx`

### Data Flowa

```d
API Request → Data Fetch → Component Render → User Display
```

---

## Layer 5: Data Sync Layer

**Purpose**: Real-time updates and integration

### Componentsa

- WebSocket server
- Event broadcasting
- Cache management
- Integration pipeline

### Filesd

- `app/websocket_manager.py` - WS connection management
- `app/main.py` - WebSocket endpoint
- `app/integrations/pipeline.py` - Sync logic

### Data Flowd

```d
Event → WebSocket Broadcast → Client Update → UI Refresh
```

---

## Technology Stack per Layer

| Layer | Backend | Frontend |
|-------|---------|----------|
| Input | FastAPI, MongoDB | Form Components |
| Categorization | Python, Redis | - |
| Analytics | PostgreSQL, Redis | Chart.js, Recharts |
| UI | REST API | React, Tailwind |
| Sync | WebSocket, Redis | React Hooks |

---

## Data Flow Architecture

```.
┌─────────────┐
│   INPUT     │ (Layer 1)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│CATEGORIZATION│ (Layer 2)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  ANALYTICS  │ (Layer 3)
└──────┬──────┘
       │
       ├──────┬──────┐
       ▼      ▼      ▼
    ┌──────┐┌──────┐┌──────┐
    │  UI  ││ SYNC││ CACHE│ (Layers 4 & 5)
    └──────┘└──────┘└──────┘
```

---

## Database Architecture

### MongoDB (Raw Data)

- `raw_email_data` - Unprocessed emails
- `parsed_transactions` - Parsed but uncategorized
- `upload_jobs` - Processing job tracking

### PostgreSQL (Clean Data)

- `transactions` - Categorized transactions
- `budgets` - User budgets
- `categories` - Category rules
- `insights` - Generated insights

### Redis (Cache & Queue)

- `stats:{user_id}` - Cached statistics
- `categories:{user_id}` - Category breakdown
- Celery task queue

---

## Security Layers

1. **Authentication**: Supabase JWT
2. **Authorization**: User-scoped queries
3. **Encryption**: TLS in transit, encryption at rest
4. **Validation**: Input sanitization
5. **Rate Limiting**: API throttling

---

## Deployment Architecture

```l
┌──────────────┐
│   Frontend   │ (Vercel/Netlify)
│   (Vite)     │
└──────┬───────┘
       │ HTTPS
       ▼
┌──────────────┐
│   Backend    │ (Railway/Render)
│   (FastAPI)  │
└──────┬───────┘
       │
       ├──► MongoDB Atlas
       ├──► Supabase (PostgreSQL)
       └──► Redis (Upstash)
```

---

## Monitoring & Observability

- **Logging**: Structured logs to centralized service
- **Metrics**: Response times, error rates
- **Alerting**: Budget thresholds, processing failures
- **Tracing**: Request ID tracking across layers

---

## Scalability Considerations

- **Horizontal**: Stateless API, multiple workers
- **Caching**: Redis for frequently accessed data
- **Async Processing**: Celery for background jobs
- **Database**: Indexed queries, connection pooling

---
