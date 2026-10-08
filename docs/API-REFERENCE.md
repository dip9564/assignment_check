# 📡 API Reference

> **Written for:** developers integrating with or testing the backend API.

The backend listens on port `8000`. FastAPI also serves interactive docs at `/docs`.

## 📋 Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Welcome message |
| GET | `/health` | Health check |
| POST | `/upload-zip` | Upload a ZIP of PDFs (replaces the current batch) |
| POST | `/analyze` | Run pairwise similarity on the uploaded batch |
| GET | `/results` | Fetch the latest saved results |
| POST | `/clear` | Delete the batch, results and highlights |
| POST | `/highlights` | Generate highlighted PDFs for two submissions |
| GET | `/highlighted/{filename}` | View a highlighted PDF |
| POST | `/api/analyze` | Web plagiarism check of one PDF |
| GET | `/api/files/{analysis_id}/{kind}` | Download a web check PDF |

## 📦 Batch comparison

### `POST /upload-zip`

Multipart form with a `file` field containing a ZIP. Returns `{"message": "New Files uploaded successfully"}`. An invalid ZIP returns `400`.

### `POST /analyze`

| Query parameter | Default | Description |
| --- | --- | --- |
| `skip_pages` | `0` | Pages to ignore at the start of each PDF |
| `ocr_enabled` | `Auto` | `OFF` disables OCR. Any other value (the UI sends `ON`) enables OCR for pages with little text |

Response:

```json
{
  "results": [
    {
      "student1": "alice",
      "student2": "bob",
      "similarity": { "tfidf": 41.2, "semantic": 88.5, "ngram": 12.0, "exact": 35.7, "final": 56.3 }
    }
  ]
}
```

`student1` and `student2` are file names without `.pdf`. Returns an empty list if fewer than two usable PDFs exist. Errors return `500`.

### `GET /results`

Returns the same `{"results": [...]}` shape from `data/result.json`, or `404` if no analysis has run.

### `POST /clear`

Removes uploads, the saved result and highlights. Returns `{"message": "Data cleared successfully"}`.

### `POST /highlights`

| Query parameter | Description |
| --- | --- |
| `student1_pdf` | First file name (`.pdf` is added if missing) |
| `student2_pdf` | Second file name |

Success response:

```json
{
  "message": "Highlighted PDFs generated",
  "student1_pdf": "alice.pdf",
  "student2_pdf": "bob.pdf",
  "matching_blocks": 4,
  "matched_words_student1": 120,
  "matched_words_student2": 120
}
```

If no text or no passages of 6+ matching words are found, the response contains only a `message` and the two paths. A missing file returns `404`.

### `GET /highlighted/{filename}`

Returns the highlighted PDF inline (`application/pdf`), or `404`.

## 🌐 Web plagiarism check

### `POST /api/analyze`

Multipart form with a `file` field (PDF, up to 25 MB and 200 pages). Requires `TAVILY_API_KEY`.

| Status | Cause |
| --- | --- |
| `400` | Not a PDF |
| `413` | File larger than 25 MB |
| `502` | Processing or Tavily failure (message included) |
| `503` | `TAVILY_API_KEY` missing or still the placeholder |

The response includes:

| Field | Meaning |
| --- | --- |
| `id`, `filename`, `created_at` | Run identifiers |
| `similarity_indicator` | Percent of searched passages that found a web result |
| `queries_checked`, `queries_with_results` | Search counts |
| `tavily_requests_used`, `tavily_request_limit` | Search budget |
| `sources` | Up to 30 sources with `url`, `title`, `domain`, `match_percentage` and `matches` |
| `unlocated_candidate_sources` | Sources dropped because their text was not found in the PDF |
| `match_groups` | Counts of `uncited_unquoted`, `quoted_without_citation`, `cited_without_quotes`, `cited_and_quoted` |
| `source_categories` | Internet, publication and submitted-work counts |
| `integrity_flags` | `non_latin_lookalikes`: count of Cyrillic and Greek characters |
| `highlight_count` | Number of highlights placed |
| `downloads` | Paths for `report`, `highlighted` and `combined` |

### `GET /api/files/{analysis_id}/{kind}`

`kind` is `report`, `highlighted` or `combined`. Returns the PDF, or `404`.
