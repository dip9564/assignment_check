from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import re
from difflib import SequenceMatcher

model = SentenceTransformer("all-MiniLM-L6-v2")


def clean_text(text):
    text = text.lower()
    return re.sub(r"[^a-z0-9]", "", text)


def prepare_ngrams(text, n=3):
    words = re.findall(r"\b\w+\b", text.lower())

    if len(words) < n:
        return set()

    return {
        " ".join(words[i:i+n])
        for i in range(len(words) - n + 1)
    }


def exact_similarity(cleaned1, cleaned2):
    if not cleaned1 or not cleaned2:
        return 0.0

    return SequenceMatcher(
        None,
        cleaned1,
        cleaned2
    ).ratio()


def ngram_similarity(set1, set2):
    if not set1 or not set2:
        return 0.0

    intersection = len(set1 & set2)

    union = len(set1) + len(set2) - intersection

    return intersection / union


def calculate_all_similarities(texts):
    # 1. TF-IDF - calculate ONCE for all documents
    vectorizer = TfidfVectorizer()

    try:
        tfidf_matrix = vectorizer.fit_transform(texts)
    except ValueError:
        tfidf_matrix = None

    # 2. Semantic embeddings
    # Only encode documents that actually contain text
    embeddings = [None] * len(texts)

    valid_texts = []
    valid_indices = []

    for i, text in enumerate(texts):
        if text.strip():
            valid_texts.append(text)
            valid_indices.append(i)

    if valid_texts:
        valid_embeddings = model.encode(
            valid_texts,
            batch_size=32,
            show_progress_bar=True,
            normalize_embeddings=True
        )

        for index, embedding in zip(
            valid_indices,
            valid_embeddings
        ):
            embeddings[index] = embedding

    # 3. Pre-calculate cleaned text
    cleaned_texts = [
        clean_text(text)
        for text in texts
    ]

    # 4. Pre-calculate ngrams

    ngram_sets = [
        prepare_ngrams(text)
        for text in texts
    ]

    tfidf_similarity_matrix = (
        cosine_similarity(tfidf_matrix)
        if tfidf_matrix is not None
        else None
    )

    return (
        tfidf_similarity_matrix,
        embeddings,
        cleaned_texts,
        ngram_sets
    )


def calculate_pair_score(i,j,tfidf_similarity_matrix,embeddings,cleaned_texts,ngram_sets):
    if tfidf_similarity_matrix is None:
        tfidf_score = 0.0
    else:
        tfidf_score = tfidf_similarity_matrix[i, j]

    # Because embeddings are normalized, dot product = cosine
    if embeddings[i] is None or embeddings[j] is None:
        semantic_score = 0.0
    else:
        semantic_score = float(
            embeddings[i] @ embeddings[j]
        )

        semantic_score = max(0.0, semantic_score)

    ngram_score = ngram_similarity(
        ngram_sets[i],
        ngram_sets[j]
    )

    exact_score = exact_similarity(
        cleaned_texts[i],
        cleaned_texts[j]
    )

    final_score = (
        0.30 * tfidf_score +
        0.40 * semantic_score +
        0.20 * ngram_score +
        0.10 * exact_score
    )

    return {
        "tfidf": round(float(tfidf_score) * 100, 2),
        "semantic": round(float(semantic_score) * 100, 2),
        "ngram": round(float(ngram_score) * 100, 2),
        "exact": round(float(exact_score) * 100, 2),
        "final": round(float(final_score) * 100, 2),
    }