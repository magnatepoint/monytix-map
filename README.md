# Monytix - Financial Command Center

A comprehensive fintech application with AI-powered insights, transaction tracking, and budget management for Indian users.

## 🚀 Features

### MVP Scope (Non-AI)

- ✅ **Rule-based categorization** (not ML-based)
- ✅ Manual transaction entry
- ✅ Email-based transaction ingestion
- ✅ File-based parsing (PDF/CSV)
- ✅ Real-time transaction updates via WebSocket
- ✅ Budget tracking and alerts
- ✅ Basic analytics and insights
- ❌ No AI/ML predictions or automation

### Backend

- **FastAPI** REST API with async support
- **Celery Workers** for background processing
- **Gmail Integration** for automatic transaction fetching
- **PDF/CSV Parsing** for bank statements (HDFC, ICICI, SBI)
- **MongoDB Atlas** for raw data storage
- **PostgreSQL/Supabase** for cleaned transaction data
- **Rule-based Categorization** using keyword matching
- **WebSocket** support for real-time updates
- **Redis** for task queue
- **SOC2-ready** security architecture

### Frontend

- **Monytix Console**: Main dashboard with financial overview
- **SpendSense**: Spending insights and analytics
- **BudgetRack**: Budget tracking with alerts
- **MoneyMoments**: Transaction timeline view
- **Supabase Auth** with Google OAuth
- **Beautiful UI** with Tailwind CSS

## 📋 Tech Stack

### Backendm

- FastAPI
- Celery
- Redis
- MongoDB Atlas
- PostgreSQL (Supabase)
- Google Gmail API
- PyPDF2, pdfplumber
- pandas
- scikit-learn

### Frontendm

- React 19
- TypeScript
- Vite
- Tailwind CSS
- Supabase Auth
- React Router
- Recharts
- Lucide Icons

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [SETUP_GUIDE.md](SETUP_GUIDE.md) | Complete setup instructions |
| [docs/FUNCTIONAL_SPECIFICATION.md](docs/FUNCTIONAL_SPECIFICATION.md) | Detailed API specs and contracts |
| [docs/FEATURE_SPECIFICATION.md](docs/FEATURE_SPECIFICATION.md) | Five-layer architecture details |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture overview |
| [backend/IMPLEMENTATION_STATUS.md](backend/IMPLEMENTATION_STATUS.md) | Current implementation status |

## 🛠️ Quick Setup

### Prerequisites

- Python 3.12+
- Node.js 18+
- Redis
- MongoDB (local or Atlas)
- PostgreSQL (Supabase or local)

### Backends

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Start Redis
redis-server

# Start Celery worker (in separate terminal)
celery -A celery_app worker --loglevel=info

# Start FastAPI
uvicorn app.main:app --reload
```

### Frontends

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env
# Edit .env with your Supabase credentials

# Start development server
npm run dev
```

## 📁 Project Structure

```m
monytix/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app
│   │   ├── models/           # Data models
│   │   ├── routers/          # API routes
│   │   ├── workers/          # Celery workers
│   │   └── database/         # DB connections
│   ├── celery_app.py         # Celery config
│   ├── config.py            # Settings
│   └── requirements.txt      # Dependencies
├── frontend/
│   ├── src/
│   │   ├── components/      # Reusable components
│   │   ├── context/         # React contexts
│   │   ├── lib/             # Utilities
│   │   ├── pages/           # Pages
│   │   └── App.tsx          # Main app
│   ├── package.json
│   └── tailwind.config.js
└── README.md
```

## 🔑 Environment Variables

### Backend (.env)

```env
MONGODB_URI=mongodb+srv://...
MONGODB_DB_NAME=monytix_rawdata
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-key
POSTGRES_URL=postgresql://...
REDIS_URL=redis://localhost:6379/0
GMAIL_CLIENT_ID=...
GMAIL_CLIENT_SECRET=...
GMAIL_REDIRECT_URI=...
JWT_SECRET_KEY=...
```

### Frontend (.env)

```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

## 🎯 Usage

1. **Sign Up**: Use Google OAuth for authentication
2. **Connect Bank**: Upload bank statements or connect Gmail
3. **View Dashboard**: See your financial overview
4. **Analyze Spending**: Use SpendSense for insights
5. **Set Budgets**: Create and track budgets in BudgetRack
6. **Timeline**: View transaction history in MoneyMoments

## 🏗️ Architecture

```m
┌─────────────────┐
│   Frontend      │ ← React + Tailwind
│   (Supabase)    │
└────────┬────────┘
         │ Auth
         ▼
┌─────────────────┐
│   FastAPI       │ ← REST API
│   (Backend)     │
└────────┬────────┘
         │
         ├──► MongoDB Atlas (raw data)
         ├──► PostgreSQL (cleaned data)
         ├──► Redis (Celery)
         └──► WebSocket (real-time)
         
┌─────────────────┐
│   Celery        │ ← Background tasks
│   Workers        │
└────────┬────────┘
         │
         ├──► Gmail fetching
         ├──► PDF parsing
         ├──► CSV parsing
         └──► ML processing
```

## 🚧 Roadmap

- [ ] Add more banks support
- [ ] Implement ML categorization training
- [ ] Add expense goals
- [ ] Export reports
- [ ] Mobile app
- [ ] Bill reminders
- [ ] Investment tracking

## 📝 License

MIT

## 🤝 Contributing

Contributions welcome! Please open an issue or submit a PR.
# monytix-map
# Force rebuild
