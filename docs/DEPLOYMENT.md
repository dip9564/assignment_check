# 🚢 Deployment

> **Written for:** people who run or host the app, such as instructors or whoever administers their server.

## 📦 Run with Docker Compose

[compose.yaml](../compose.yaml) starts two containers from prebuilt images.

| Service | Image | Port |
| --- | --- | --- |
| `backend` | `dip9564/assignment-backend:latest` | 8000 |
| `frontend` | `dip9564/assignment-frontend:latest` | 8501 |

1. Create a `.env` file in the same folder as `compose.yaml`.
2. Run `docker compose up -d`.
3. Open <http://localhost:8501>.

To stop: `docker compose down`.

## ⚙️ Configuration

The backend reads `.env` through `env_file`. The frontend gets `API_URL` from `compose.yaml`.

| Variable | Used by | Default | Description |
| --- | --- | --- | --- |
| `TAVILY_API_KEY` | Backend | none | Needed only for the web plagiarism check |
| `TAVILY_QUERY_BUDGET` | Backend | `6` | Searches per web check, limited to 1-18 |
| `TAVILY_MAX_RESULTS` | Backend | `3` | Results per search, limited to 1-5 |
| `DATA_DIR` | Backend | `data` | Data folder setting read by `reports.py` |
| `API_URL` | Frontend | `http://127.0.0.1:8000` | Backend address (`http://backend:8000` in Compose) |

Example `.env`:

```env
TAVILY_API_KEY=your-key-here
TAVILY_QUERY_BUDGET=6
TAVILY_MAX_RESULTS=3
```

> [!NOTE]
> Without `TAVILY_API_KEY`, batch comparison still works. Only the Plagiarism Report tab fails (HTTP 503).

## 💽 Persistent data

Compose mounts `./uploads` and `./data` into the backend, so uploads and results survive restarts. Delete those folders (or use **Clear** in the app) to remove student files.

> [!IMPORTANT]
> Uploaded assignments are stored unencrypted on the host. Handle them according to your institution's data policy.

## 🛠️ Build from source

Build the images from the repo folders:

```bash
docker build -t dip9564/assignment-backend:latest ./backend
docker build -t dip9564/assignment-frontend:latest ./frontend
```

The backend image installs Tesseract OCR and CPU-only PyTorch 2.5.1, so the build is large and slow.

## 💻 Run without Docker

You need Python 3.11 and, for OCR, the Tesseract binary on your `PATH`.

1. Backend:

   ```bash
   cd backend
   pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
   pip install -r requirements.txt
   uvicorn app:app --port 8000
   ```

2. Frontend, in a second terminal:

   ```bash
   cd frontend
   pip install -r requirements.txt
   streamlit run app.py
   ```

The first backend start downloads the `all-MiniLM-L6-v2` model, so it needs internet access.

## 🩺 Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| "Can't connect to backend" | Backend is not running, or `API_URL` is wrong |
| Analysis times out | Large batch. The UI waits up to 30 minutes. Try OCR off if the PDFs have selectable text |
| A PDF is missing from results | It is not a valid PDF, or has under 10 characters of text after skipped pages |
| Web check returns 503 | `TAVILY_API_KEY` is missing |
| Web check says no selectable text | The PDF is scanned. OCR it first |
