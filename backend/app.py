from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import zipfile, os, shutil, json
import fitz
import pytesseract
from PIL import Image
from similarity import (
    calculate_all_similarities,
    calculate_pair_score
)


UPLOAD_DIR = "uploads/submissions"
ZIP_PATH = "uploads/submissions.zip"
RESULT_FILE = "data/result.json"


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

def extract_from_pdf(file_path, skip_pages):
    document = fitz.open(file_path)

    pages = []
    for page in document[skip_pages:]:
        pages.append(page.get_text())

    document.close()
    return "\n".join(pages)

def extract_text_from_flattened_pdf(file_path, skip_pages):
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
                            
                        submissions.append({
                            "filename": os.path.splitext(filename)[0],
                            "text": text
                     })

        results = calculate_similarity(submissions)
        save_result(results)

        if os.path.exists(UPLOAD_DIR):  # clear the upload directory after analysis
            shutil.rmtree(UPLOAD_DIR)

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

    return {"message": "Data cleared successfully"}