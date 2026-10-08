# 🔍 Assignment Check

A web app that helps instructors spot potentially copied work. It compares a batch of student PDF assignments against each other, and can also check a single PDF against the internet.

Similarity scores are a signal for manual review, not proof of plagiarism.

## ✨ Features

- **Batch comparison:** upload a ZIP (or several PDFs) and get a pairwise similarity score for every pair of submissions.
- **Four techniques combined:** TF-IDF, semantic embeddings, word 3-gram overlap and exact character matching.
- **OCR support:** optional Tesseract OCR for scanned PDFs.
- **Side-by-side highlights:** matching passages are highlighted in both PDFs.
- **Overview tools:** score tables, distribution charts and a network graph of highly similar students.
- **Web plagiarism report:** check one PDF against web search results (Tavily) and download a report, a highlighted copy, or both combined.

## 🧱 Tech stack

| Part | Technology |
| --- | --- |
| Backend | Python 3.11, FastAPI, scikit-learn, sentence-transformers (`all-MiniLM-L6-v2`), PyMuPDF, Tesseract, ReportLab |
| Frontend | Streamlit, pandas, pyvis |
| Packaging | Docker, Docker Compose |

## 🚀 Quick start

1. Create a `.env` file next to `compose.yaml` (see [Deployment](docs/DEPLOYMENT.md) for the variables).
2. Start both services:

   ```bash
   docker compose up -d
   ```

3. Open the app at <http://localhost:8501>. The API runs at <http://localhost:8000> (interactive docs at `/docs`).

## 🗂️ Project layout

```text
assignment_check/
├── backend/            FastAPI service
│   ├── app.py          API routes, PDF/ZIP handling, OCR
│   ├── similarity.py   Pairwise scoring
│   ├── highlight.py    Matching passages and PDF highlighting
│   └── reports.py      Web plagiarism check and PDF reports
├── frontend/           Streamlit UI
│   ├── app.py          Pages and tabs
│   └── helper.py       Tables, charts and graph helpers
└── compose.yaml        Runs both services
```

## 📚 Documentation guide

| Doc | Read it for |
| --- | --- |
| [docs/BATCH-COMPARISON-FLOW.md](docs/BATCH-COMPARISON-FLOW.md) | Step-by-step working of the main feature: upload, text extraction, scoring, charts and highlighting |
| [docs/WEB-PLAGIARISM-FLOW.md](docs/WEB-PLAGIARISM-FLOW.md) | Step-by-step working of the web check: passage selection, search, source matching and report |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the components fit together and how the scores are computed |
| [docs/API-REFERENCE.md](docs/API-REFERENCE.md) | Every backend endpoint with parameters and responses |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Running, configuring and troubleshooting the app |

## 📄 License

See [LICENSE](LICENSE).
