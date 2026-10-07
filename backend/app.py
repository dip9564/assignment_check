from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import zipfile, os, shutil, json
import fitz
import pytesseract
from PIL import Image
import uuid
from datetime import datetime, timezone
from pathlib import Path
import requests
from typing import Any
from similarity import (
    calculate_all_similarities,
    calculate_pair_score
)
from highlight import get_highlights
from reports import mark_pages, make_report, merge_pdfs, analyze_text, normalize, content_page_indexes, clear_previous_run,sources_with_locatable_text


UPLOAD_DIR = "uploads/submissions"
ZIP_PATH = "uploads/submissions.zip"
RESULT_FILE = "data/result.json"
HIGHLIGHT_DIR = "uploads/highlighted"

WEB_UPLOAD_DIR = Path("uploads/web")
RESULT_DIR = Path("data/results")

MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_PAGES = 200

def save_result(data):
    os.makedirs("data", exist_ok=True)

    with open(RESULT_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)

def clean_upload_directory():
    for root, dirs, files in os.walk(UPLOAD_DIR, topdown=False):
        for filename in files:

            file_path = os.path.join(root, filename)
            if filename.startswith("._"):
                os.remove(file_path)
                continue

            if not filename.lower().endswith(".pdf"):
                os.remove(file_path)

        for dirname in dirs:
            dir_path = os.path.join(root, dirname)

            if not os.listdir(dir_path):
                os.rmdir(dir_path)


def calculate_similarity(submissions):

    if len(submissions) < 2:
        return []

    # Get all texts
    texts = [submission["text"]for submission in submissions]
    # Calculate expensive things ONCE
    (tfidf_matrix,embeddings,cleaned_texts,ngram_sets) = calculate_all_similarities(texts)

    results = []

    for i in range(len(submissions)):
        for j in range(i + 1, len(submissions)):

            score = calculate_pair_score(i,j,tfidf_matrix,embeddings,cleaned_texts,ngram_sets)

            results.append({
                "student1": submissions[i]["filename"],
                "student2": submissions[j]["filename"],
                "similarity": score
            })

    return results


def is_valid_pdf(file_path):
    try:
        with open(file_path, "rb") as f:
            return f.read(5) == b"%PDF-"
    except Exception:
        return False


def extract_from_pdf(file_path, skip_pages):
    if not is_valid_pdf(file_path):
        print(f"Skipping invalid PDF: {file_path}")
        return None
    
    document = fitz.open(file_path)

    pages = []
    for page in document[skip_pages:]:
        pages.append(page.get_text())

    document.close()
    return "\n".join(pages)


def extract_text_from_flattened_pdf(file_path, skip_pages):
    if not is_valid_pdf(file_path):
        print(f"Skipping invalid PDF: {file_path}")
        return None
    document = fitz.open(file_path)

    pages = []
    for page in document[skip_pages:]:
        page_text = page.get_text().strip()

        # Only OCR pages that have almost no usable text
        if len(page_text) < 30:
            pix = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6),alpha=False)
            image = Image.frombytes("RGB",[pix.width, pix.height],pix.samples)
            page_text = pytesseract.image_to_string(image,config="--psm 6")

        pages.append(page_text)

    document.close()
    return "\n".join(pages)


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Assignment Submission API"}

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.post("/upload-zip")
async def upload_zip(file: UploadFile = File(...)):
    os.makedirs("uploads", exist_ok=True)

    with open(ZIP_PATH, "wb") as f:
        f.write(await file.read())

    if not zipfile.is_zipfile(ZIP_PATH): # check is actually a zip file
        os.remove(ZIP_PATH)
        raise HTTPException(status_code=400, detail={"message": "Invalid ZIP file"})

    if os.path.exists(UPLOAD_DIR): # delete the existing directory if it exists
        shutil.rmtree(UPLOAD_DIR)

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    with zipfile.ZipFile(ZIP_PATH, "r") as zip_ref:
        zip_ref.extractall(UPLOAD_DIR)
    
    os.remove(ZIP_PATH)
    clean_upload_directory()

    return {"message": "New Files uploaded successfully"}


@app.post("/analyze")
async def analyze(skip_pages: int = 0, ocr_enabled: str = "Auto"):
    submissions = []
    try:
        for root, dirs, files in os.walk(UPLOAD_DIR):
            for filename in files:
                    if filename.lower().endswith(".pdf"):
                        file_path = os.path.join(root, filename)

                        if  ocr_enabled == "OFF":
                            text = extract_from_pdf(file_path,skip_pages)
                        else:
                            text = extract_text_from_flattened_pdf(file_path, skip_pages)

                        if text is None or len(text.strip()) < 10:
                            print(f"Skipping {filename} due to insufficient text.")
                            continue 
                        
                        submissions.append({
                            "filename": os.path.splitext(filename)[0],
                            "text": text
                     })

        results = calculate_similarity(submissions)
        save_result(results)

        return {"results": results}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail={"message": f"{str(e)}"})


@app.get("/results",response_model=dict)
def get_results():  
    if not os.path.exists(RESULT_FILE):
        raise HTTPException(status_code=404, detail={"message": "No results found. Please run the analysis first."})

    with open(RESULT_FILE, "r", encoding="utf-8") as file:
        results = json.load(file)

    return {"results": results}


@app.post("/clear")
def clear_data():
    if os.path.exists(UPLOAD_DIR):
        shutil.rmtree(UPLOAD_DIR)
    if os.path.exists(ZIP_PATH):
        os.remove(ZIP_PATH)
    if os.path.exists(RESULT_FILE):
        os.remove(RESULT_FILE)
    if os.path.exists(HIGHLIGHT_DIR):
        shutil.rmtree(HIGHLIGHT_DIR)

    return {"message": "Data cleared successfully"}


@app.post("/highlights")
def get_highlights_endpoint(student1_pdf: str, student2_pdf: str):

    if not student1_pdf.lower().endswith(".pdf"):
        student1_pdf += ".pdf"

    if not student2_pdf.lower().endswith(".pdf"):
        student2_pdf += ".pdf"

    student1_path = None
    student2_path = None

    for root, dirs, files in os.walk(UPLOAD_DIR):
        for filename in files:

            if filename.lower().endswith(".pdf"):

                if filename == student1_pdf:
                    student1_path = os.path.join(root, filename)

                if filename == student2_pdf:
                    student2_path = os.path.join(root, filename)

    if student1_path is None:
        raise HTTPException(
            status_code=404,
            detail=f"Student 1 PDF not found: {student1_pdf}"
        )

    if student2_path is None:
        raise HTTPException(
            status_code=404,
            detail=f"Student 2 PDF not found: {student2_pdf}"
        )

    return get_highlights(student1_path, student2_path)


@app.get("/highlighted/{filename}")
def get_highlighted_pdf(filename: str):

    file_path = os.path.join(
        "uploads",
        "highlighted",
        filename
    )

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail="Highlighted PDF not found"
        )

    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename=filename,
        content_disposition_type="inline"
    )


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)) -> dict[str, Any]:
    if file.content_type != "application/pdf" and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Upload a PDF file.")
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key or api_key == "tvly-your-key-here":
        raise HTTPException(503, "Tavily API key is not configured. Add TAVILY_API_KEY to .env and restart the API.")
    payload = await file.read(MAX_FILE_BYTES + 1)
    if len(payload) > MAX_FILE_BYTES:
        raise HTTPException(413, "PDF must be 25 MB or smaller.")
    clear_previous_run()
    analysis_id = str(uuid.uuid4())
    safe_name = Path(file.filename or "upload.pdf").name
    source_path = WEB_UPLOAD_DIR / f"{analysis_id}.pdf"
    source_path.write_bytes(payload)
    try:
        pdf = fitz.open(source_path)
        if pdf.page_count > MAX_PAGES:
            pdf.close()
            raise ValueError(f"PDF exceeds the {MAX_PAGES}-page limit.")
        pages = [page.get_text("text") for page in pdf]
        pdf.close()
        if not any(normalize(p) for p in pages):
            raise ValueError("No selectable text found. This appears to be a scanned PDF; OCR it before uploading.")
        permitted_pages = content_page_indexes(pages)
        content_pages = [page_text for index, page_text in enumerate(pages) if index in permitted_pages]
        if not content_pages:
            raise ValueError("No document content was found before the References section.")
        result = analyze_text(content_pages, api_key)
        all_candidate_sources = result["sources"]
        located_sources = sources_with_locatable_text(source_path, all_candidate_sources, permitted_pages)
        result["sources"] = located_sources
        result["unlocated_candidate_sources"] = len(all_candidate_sources) - len(located_sources)
        result["source_categories"]["internet_sources"] = len(located_sources)
        result.update({"id": analysis_id, "filename": safe_name, "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "highlight_count": 0})
        highlighted = RESULT_DIR / f"{analysis_id}_highlighted.pdf"
        result["highlight_count"] = mark_pages(source_path, result["sources"], permitted_pages, highlighted)
        report = RESULT_DIR / f"{analysis_id}_report.pdf"
        make_report(result, safe_name, report)
        combined = RESULT_DIR / f"{analysis_id}_combined.pdf"
        merge_pdfs([report, highlighted], combined)
        result["downloads"] = {"report": f"/api/files/{analysis_id}/report", "highlighted": f"/api/files/{analysis_id}/highlighted", "combined": f"/api/files/{analysis_id}/combined"}
        return result
    except requests.RequestException as exc:
        message = f"Tavily request failed: {exc}"
    except Exception as exc:
        message = str(exc)
    source_path.unlink(missing_ok=True)
    raise HTTPException(502, message)


@app.get("/api/files/{analysis_id}/{kind}")
def download_file(analysis_id: str, kind: str) -> FileResponse:
    allowed = {"report": "report", "highlighted": "highlighted", "combined": "combined"}
    if kind not in allowed:
        raise HTTPException(404, "File not found.")
    
    path = RESULT_DIR / f"{analysis_id}_{allowed[kind]}.pdf"
    if not path.is_file():
        raise HTTPException(404, "File not found.")
    
    return FileResponse(path, media_type="application/pdf", filename=f"{kind}.pdf")
