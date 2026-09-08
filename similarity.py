from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import re
from difflib import SequenceMatcher


model = SentenceTransformer("all-MiniLM-L6-v2")


def tfidf_similarity(text1, text2):

    if not text1.strip() or not text2.strip():
        return 0.0

    try:
        vectorizer = TfidfVectorizer()
        vectors = vectorizer.fit_transform([text1,text2])
        score = cosine_similarity(vectors[0],vectors[1])[0][0]

        return float(score)
    
    except ValueError:
        return 0.0


def semantic_similarity(text1, text2):
    if not text1.strip() or not text2.strip():
        return 0.0
    
    embeddings = model.encode([text1, text2])
    score = cosine_similarity([embeddings[0]],[embeddings[1]])[0][0]
    return max(0.0, score)


def clean_text(text):
    text = text.lower()
    # Keep only letters and numbers (removes spaces, tabs, newlines, and punctuation)
    only_alphanumeric = re.sub(r'[^a-z0-9]', '', text)
    return only_alphanumeric

def exact_similarity(text1, text2):
    text1 = clean_text(text1)
    text2 = clean_text(text2)

    if not text1 or not text2:
        return 0.0
    
    similarity = SequenceMatcher(None, text1, text2).ratio()
    return similarity


def ngram_similarity(text1, text2, n=3):

    words1 = re.findall(r"\b\w+\b", text1.lower())
    words2 = re.findall(r"\b\w+\b", text2.lower())

    ngrams1 = set(
        tuple(words1[i:i+n])
        for i in range(len(words1) - n + 1)
    )

    ngrams2 = set(
        tuple(words2[i:i+n])
        for i in range(len(words2) - n + 1)
    )

    if not ngrams1 or not ngrams2:
        return 0.0

    intersection = ngrams1.intersection(ngrams2)
    union = ngrams1.union(ngrams2)
    return len(intersection) / len(union)


def compare_text(text1, text2):

    tfidf_score = float(tfidf_similarity(text1, text2))
    semantic_score = float(semantic_similarity(text1, text2))
    ngram_score = float(ngram_similarity(text1, text2))
    exact_score = float(exact_similarity(text1, text2))

    final_score = (
            0.30 * tfidf_score +
            0.40 * semantic_score +
            0.20 * ngram_score+
            0.10 * exact_score
        )
    
    return {
        "tfidf": round(tfidf_score * 100, 2),
        "semantic": round(semantic_score * 100, 2),
        "ngram": round(ngram_score * 100, 2),
        "exact": round(exact_score * 100, 2),
        "final": round(float(final_score) * 100, 2),
    }