# DravyaSense

**PCA and t-SNE-based visualization of electronic-tongue sensor data for herbal (Dravya) category separation.**

DravyaSense is an unsupervised machine learning web application. Upload multi-channel electronic-tongue sensor datasets, preprocess them, apply PCA and t-SNE, and explore whether known herbal categories produce distinguishable patterns in reduced-dimensional space.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 · TypeScript · Vite · Tailwind CSS · Plotly.js |
| Backend | Python 3.11+ · FastAPI · Uvicorn |
| ML | Scikit-learn · SciPy · Pandas · NumPy |
| Database | SQLite (dev) · PostgreSQL (prod) |
| ORM | SQLAlchemy 2 (async) |

---

## Project Structure

```
Unsupervised(bopii)/
├── frontend/          # React + TypeScript + Vite frontend
├── backend/           # FastAPI Python backend
├── demo_data/         # Clearly labeled demonstration datasets
├── docs/              # API reference and documentation
└── README.md
```

---

## Local Development Setup

### Prerequisites

- **Node.js** ≥ 20 and **npm** ≥ 10
- **Python** ≥ 3.11

---

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at **http://localhost:5173**

All `/api/*` requests are automatically proxied to the backend at `http://localhost:8000`.

Other available scripts:

```bash
npm run build     # Production build → dist/
npm run preview   # Serve the production build locally
```

---

### Backend

```bash
cd backend

# Create and activate the virtual environment
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# (Optional) copy and edit environment variables
cp .env.example .env

# Start the development server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The backend runs at **http://localhost:8000**

- API documentation (Swagger): http://localhost:8000/api/docs
- Alternative docs (ReDoc): http://localhost:8000/api/redoc
- Health check: http://localhost:8000/api/health

---

### Running Both Together

Open two terminal windows:

**Terminal 1 — Backend:**
```bash
cd backend
.venv\Scripts\Activate.ps1    # Windows
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

Then open http://localhost:5173 in your browser.

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and adjust as needed.

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | Environment name |
| `APP_VERSION` | `0.1.0` | API version string |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/dravyasense.db` | Database connection URL |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed frontend origins |
| `UPLOAD_DIR` | `./uploads` | Directory for uploaded files |
| `MAX_UPLOAD_SIZE_MB` | `50` | Maximum upload file size |

---

## Scientific Notes

- Category labels are **never** used as sensor features. They are used only for label-assisted evaluation metrics (silhouette score, Davies-Bouldin index).
- All visualizations are driven by real uploaded data. No synthetic results are displayed.
- Demonstration datasets in `demo_data/` are clearly labeled as such.
- PCA and t-SNE operate only on detected sensor columns. Sample ID columns are excluded automatically.

---

## Development Milestones

| Day | Module |
|---|---|
| 1 | Project scaffold (this day) |
| 2 | Dataset upload and management |
| 3 | Data Explorer |
| 4 | Preprocessing Studio |
| 5–6 | PCA analysis and visualization |
| 8–9 | t-SNE analysis and visualization |
| 10 | PCA vs t-SNE comparison |
| 11 | Category separation evaluation |
| 12 | Experiment history |
| 13 | Research insights and reports |
| 14 | Landing page polish, QA, deployment prep |

---

## License

Research project — all rights reserved.
