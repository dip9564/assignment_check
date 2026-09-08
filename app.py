from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import zipfile, os, shutil, json
import fitz
from assignment_check.similarity import compare_text


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
    results = []
    for i in range(len(submissions)):
        for j in range(i + 1, len(submissions)):

            text1 = submissions[i]["text"]
            text2 = submissions[j]["text"]
            score = compare_text(text1, text2)

            results.append({
                "student1": submissions[i]["filename"],
                "student2": submissions[j]["filename"],
                "similarity": score
            })
    return results

def extract_text_from_pdf(file_path, skip_pages):
    document = fitz.open(file_path)

    text = ""
    for page in document[skip_pages:]:
        text += page.get_text()

    document.close()
    return text


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For testing
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
async def analyze(skip_pages: int = 0):
    submissions = []
    try:
        for root, dirs, files in os.walk(UPLOAD_DIR):
            for filename in files:
                    if filename.lower().endswith(".pdf"):
                        file_path = os.path.join(root, filename)

                        text = extract_text_from_pdf(file_path,skip_pages)
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