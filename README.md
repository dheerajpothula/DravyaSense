# DravyaSense
### Unsupervised Analysis and Visualization of Electronic-Tongue Sensor Data for Herbal Category Separation

---

## Overview

**DravyaSense** is an unsupervised machine learning platform developed to investigate patterns and potential category separation in multi-channel electronic-tongue sensor data associated with herbal (*Dravya*) samples.

The application provides an integrated analytical environment for uploading experimental datasets, performing data preprocessing, applying dimensionality reduction techniques, and visualizing high-dimensional sensor measurements.

Using **Principal Component Analysis (PCA)** and **t-Distributed Stochastic Neighbor Embedding (t-SNE)**, DravyaSense enables researchers to explore underlying data structures, identify potential groupings, and examine similarities and differences among herbal sample categories.

The platform emphasizes data-driven exploration, reproducible analysis, and scientifically responsible interpretation of sensor measurements.

## Core Capabilities

| Module | Description |
|---|---|
| Dataset Management | Upload, validate, and manage electronic-tongue sensor datasets. |
| Data Exploration | Examine sensor measurements, sample distributions, and statistical summaries. |
| Data Preprocessing | Handle missing values, feature selection, normalization, and scaling. |
| PCA Analysis | Identify dominant variance patterns and generate lower-dimensional representations. |
| t-SNE Analysis | Explore nonlinear relationships and local structures within sensor measurements. |
| Interactive Visualization | Analyze 2D and 3D representations using interactive Plotly visualizations. |
| Category Evaluation | Examine potential category separation using quantitative evaluation metrics. |
| Experiment Management | Maintain and compare previous analytical experiments. |
| Research Reporting | Present analytical findings through visual summaries and research-oriented reports. |

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite |
| UI Framework | Tailwind CSS |
| Visualization | Plotly.js |
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Machine Learning | Scikit-learn, SciPy |
| Data Processing | Pandas, NumPy |
| Database | SQLite (Development), PostgreSQL (Production) |
| ORM | SQLAlchemy 2 (Async) |

## System Architecture

DravyaSense follows a modular frontend-backend architecture that separates user interaction, analytical processing, visualization, and data persistence.

```text
                    DravyaSense
                         |
             +-----------+-----------+
             |                       |
          Frontend                 Backend
       React + TypeScript          FastAPI
             |                       |
       Dataset Upload          Data Validation
             |                       |
       Data Exploration        Preprocessing
             |                       |
             |                Sensor Features
             |                       |
             |              Dimensionality Reduction
             |                   /       \
             |                 PCA       t-SNE
             |                   \       /
             |                 Evaluation
             |                       |
             +-----------------------+
                         |
               Interactive Results
                         |
                  Plotly Visuals
                         |
                 Experiment Storage
                    SQLite / PostgreSQL
```

## Project Structure

```text
DravyaSense/
│
├── frontend/
│   └── React + TypeScript + Vite application
│
├── backend/
│   ├── app/
│   │   └── FastAPI application
│   ├── requirements.txt
│   └── .env.example
│
├── demo_data/
│   └── Demonstration sensor datasets
│
├── docs/
│   └── API reference and documentation
│
└── README.md
```

## Installation and Setup

### Prerequisites

Ensure the following dependencies are installed:

- Node.js 20 or later
- npm 10 or later
- Python 3.11 or later
- Git

### Repository Setup

```bash
git clone <repository-url>
cd DravyaSense
```

### Backend Configuration

Navigate to the backend directory:

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate the environment.

**Windows PowerShell:**

```powershell
.venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
source .venv/bin/activate
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Configure the environment:

```bash
cp .env.example .env
```

Start the backend:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend Configuration

Open a separate terminal and navigate to the frontend directory:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

The frontend and backend are now available for local development.

## Environment Configuration

Backend configuration is managed through environment variables.

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | Application environment |
| `APP_VERSION` | `0.1.0` | Application version |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/dravyasense.db` | Database connection string |
| `CORS_ORIGINS` | `http://localhost:5173` | Permitted frontend origins |
| `UPLOAD_DIR` | `./uploads` | Dataset upload directory |
| `MAX_UPLOAD_SIZE_MB` | `50` | Maximum permitted upload size |

## Scientific Methodology

DravyaSense employs dimensionality reduction to investigate the structure of high-dimensional electronic-tongue sensor measurements.

### 1. Principal Component Analysis (PCA)

PCA is a linear dimensionality reduction technique that transforms correlated sensor measurements into a set of orthogonal principal components.

The primary objectives are:

- Identify the directions of maximum variance.
- Reduce the dimensionality of sensor measurements.
- Examine dominant patterns across herbal samples.
- Visualize potential differences between sample categories.

### 2. t-Distributed Stochastic Neighbor Embedding (t-SNE)

t-SNE is a nonlinear dimensionality reduction technique designed to preserve local neighborhood relationships when mapping high-dimensional observations into lower-dimensional space.

Its application within DravyaSense includes:

- Exploring local similarities among sensor observations.
- Investigating potential sample groupings.
- Identifying nonlinear structures.
- Visualizing complex sensor-response relationships.

### 3. Category Separation Evaluation

The application incorporates quantitative metrics to investigate the quality of category separation in reduced-dimensional representations.

| Metric | Purpose |
|---|---|
| Silhouette Score | Evaluates cluster cohesion and separation. |
| Davies-Bouldin Index | Measures similarity between clusters based on their dispersion and separation. |

**Interpretation:** These metrics provide complementary perspectives on the structure of the resulting representations. Their interpretation depends on the representation, distance metric, and evaluation procedure.

## Data Integrity and Research Considerations

Scientific reliability and analytical transparency are fundamental principles of DravyaSense.

- **Feature Isolation:** Category labels are excluded from sensor feature matrices.
- **Metadata Exclusion:** Sample identifiers and non-sensor metadata are not treated as measurement features.
- **Sensor-Based Analysis:** PCA and t-SNE operate exclusively on detected sensor measurement columns.
- **Label-Assisted Evaluation:** Known category labels are reserved for visualization and evaluation, not used as input features.
- **Data Authenticity:** Analytical visualizations are generated from uploaded datasets.
- **Demonstration Transparency:** Demonstration datasets are explicitly identified and distinguished from experimental datasets.
- **Reproducibility:** Analytical configurations and experiment results are intended to support consistent research workflows.

**Scientific Limitation:** PCA and t-SNE are exploratory visualization techniques. Apparent separation in reduced-dimensional space does not independently establish chemical identity, validate herbal classification, or demonstrate statistical significance.

## Project Objectives

1. Develop a unified analytical platform for electronic-tongue sensor datasets.
2. Apply unsupervised dimensionality reduction to high-dimensional sensor measurements.
3. Investigate potential patterns and category separation among herbal samples.
4. Evaluate reduced-dimensional representations using quantitative metrics.
5. Provide interactive visualizations to support scientific exploration and interpretation.
6. Establish a foundation for further research in electronic-tongue-based herbal analysis.

## Project Information

| Attribute | Description |
|---|---|
| Project Name | DravyaSense |
| Project Domain | Electronic-Tongue Sensor Data Analysis |
| Project Category | Unsupervised Machine Learning |
| Primary Techniques | PCA and t-SNE |
| Programming Languages | Python and TypeScript |
| Frontend Architecture | React |
| Backend Architecture | FastAPI |
| Data Processing | Pandas and NumPy |
| Database | SQLite and PostgreSQL |
| Primary Application | Dimensionality Reduction and Data Visualization |

## License and Usage

DravyaSense is developed as an academic and research-oriented software project.

All rights reserved. Reproduction, redistribution, modification, or commercial use requires prior authorization from the project owner.

---

<p align="center">
  <strong>DravyaSense</strong><br>
  <em>Exploring Herbal Sensor Patterns Through Unsupervised Learning.</em>
</p>
