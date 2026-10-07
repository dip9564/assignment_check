from __future__ import annotations
import os
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import fitz
import requests
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(os.getenv("DATA_DIR", "data")).resolve()
WEB_UPLOAD_DIR = Path("uploads/web")
RESULT_DIR = Path("data/results")

for folder in (WEB_UPLOAD_DIR, RESULT_DIR):
    folder.mkdir(parents=True, exist_ok=True)

TAVILY_URL = "https://api.tavily.com/search"

SOURCE_COLORS = ["#c91675", "#2764c6", "#00804c", "#7333e6", "#d21173", "#b66a00", "#087f8c"]
TAVILY_QUERY_BUDGET = max(1, min(int(os.getenv("TAVILY_QUERY_BUDGET", "6")), 18))
TAVILY_MAX_RESULTS = max(1, min(int(os.getenv("TAVILY_MAX_RESULTS", "3")), 5))


def clear_previous_run() -> None:
    for folder in (WEB_UPLOAD_DIR, RESULT_DIR):
        for path in folder.glob("*"):
            if path.is_file():
                path.unlink()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# Exclude the References/Bibliography section and all pages after it
def content_page_indexes(pages: list[str]) -> set[int]:
    heading = re.compile(r"(?im)^\s*(references|bibliography|works\s+cited)\s*$")
    for index, page_text in enumerate(pages):
        if heading.search(page_text):
            return set(range(index))
    return set(range(len(pages)))


# Choose searchable passages across the full PDF, with page coverage first
def sentence_chunks(pages: list[str], limit: int = 18) -> list[str]:
    candidates_by_page: list[list[str]] = []
    for page_text in pages:
        sentences = [normalize(s) for s in re.split(r"(?<=[.!?])\s+", page_text) if len(normalize(s)) >= 50]
        page_chunks = []

        for start in range(0, len(sentences), 3):
            chunk = " ".join(sentences[start:start + 3])
            if len(chunk) >= 90:
                page_chunks.append(chunk[:900])
        candidates_by_page.append(page_chunks)

    all_candidates = [chunk for page_chunks in candidates_by_page for chunk in page_chunks]
    if len(all_candidates) <= limit:
        return all_candidates

    # Give every text-bearing page one query whenever the budget permits, then
    # spread remaining queries through the whole document.
    page_representatives = [page_chunks[0] for page_chunks in candidates_by_page if page_chunks]
    if len(page_representatives) >= limit:
        positions = [round(index * (len(page_representatives) - 1) / (limit - 1)) for index in range(limit)]
        return [page_representatives[position] for position in dict.fromkeys(positions)]
    
    remaining = limit - len(page_representatives)
    representative_set = set(page_representatives)
    extra_candidates = [chunk for chunk in all_candidates if chunk not in representative_set]

    if not extra_candidates:
        return page_representatives
    
    positions = [round(index * (len(extra_candidates) - 1) / max(remaining - 1, 1)) for index in range(min(remaining, len(extra_candidates)))]
    return page_representatives + [extra_candidates[position] for position in dict.fromkeys(positions)]


def search_tavily(query: str, api_key: str) -> list[dict[str, Any]]:
    response = requests.post(TAVILY_URL, json={
        "api_key": api_key, "query": query, "search_depth": "basic",
        "max_results": TAVILY_MAX_RESULTS, "include_answer": False, "include_raw_content": False,
    }, timeout=45)
    response.raise_for_status()
    return response.json().get("results", [])


# Select the submitted sentence most similar to Tavily's returned snippet
def best_matching_sentence(query: str, source_snippet: str) -> str:
    sentences = [normalize(sentence) for sentence in re.split(r"(?<=[.!?])\s+", query) if len(normalize(sentence)) >= 20]
    if not sentences or not source_snippet:
        return sentences[0] if sentences else query
    
    snippet = normalize(source_snippet).lower()
    snippet_words = set(re.findall(r"\w+", snippet))

    def score(sentence: str) -> float:
        sentence_lower = sentence.lower()
        words = set(re.findall(r"\w+", sentence_lower))
        overlap = len(words & snippet_words) / max(len(words), 1)
        sequence = SequenceMatcher(None, sentence_lower, snippet).ratio()
        return overlap * 0.7 + sequence * 0.3
    
    return max(sentences, key=score)


def analyze_text(pages: list[str], api_key: str) -> dict[str, Any]:
    full_text = "\n".join(pages)
    chunks = sentence_chunks(pages, limit=TAVILY_QUERY_BUDGET)

    if not chunks:
        raise ValueError("Not enough extractable text to search. This may be a scanned PDF; run OCR and upload a searchable PDF.")
    
    candidates: dict[str, dict[str, Any]] = {}
    for query in chunks:
        for item in search_tavily(query, api_key):
            url = item.get("url", "")
            if not url:
                continue

            key = url.split("#")[0]
            record = candidates.setdefault(key, {"url": key, "title": item.get("title", key), "content": item.get("content", ""), "score": 0.0, "matches": []})
            record["score"] = max(record["score"], float(item.get("score") or 0))
            
            if len(record["content"]) < len(item.get("content", "")):
                record["content"] = item.get("content", "")

            record["matches"].append({"query": query, "search_score": float(item.get("score") or 0)})

    # Report is explicit that this is search-result overlap evidence, not an exhaustive verdict.
    source_list = sorted(candidates.values(), key=lambda x: (len(x["matches"]), x["score"]), reverse=True)
    
    for source in source_list:
        for match in source["matches"]:
            match["passage"] = best_matching_sentence(match["query"], source.get("content", ""))

        source["matches"] = source["matches"][:8]

    # A rough indicator: fraction of submitted passages that returned a web result.
    found_queries = {m["query"] for s in source_list for m in s["matches"]}
    similarity = round(100 * len(found_queries) / len(chunks)) if chunks else 0
    matched_passages = [chunk for chunk in chunks if chunk in found_queries]

    def has_citation(passage: str) -> bool:
        return bool(re.search(r"(?:\[[^\]]{1,50}\]|\([^)]{1,70}\b(?:19|20)\d{2}[a-z]?[^)]*\))", passage))

    def has_quotes(passage: str) -> bool:
        return bool(re.search(r'["“”‘’]|\'[^\']{12,}\'', passage))

    groups = {
        "uncited_unquoted": 0,
        "quoted_without_citation": 0,
        "cited_without_quotes": 0,
        "cited_and_quoted": 0,
    }
    for passage in matched_passages:
        cited, quoted = has_citation(passage), has_quotes(passage)
        if cited and quoted:
            groups["cited_and_quoted"] += 1
        elif cited:
            groups["cited_without_quotes"] += 1
        elif quoted:
            groups["quoted_without_citation"] += 1
        else:
            groups["uncited_unquoted"] += 1

    foreign_lookalikes = sum(1 for char in full_text if "CYRILLIC" in __import__("unicodedata").name(char, "") or "GREEK" in __import__("unicodedata").name(char, ""))
    for source in source_list:
        source["source_type"] = "Internet"
        source["domain"] = urlparse(source["url"]).netloc.removeprefix("www.") or source["url"]
        source["match_percentage"] = round(100 * len(source["matches"]) / len(chunks), 1)
    
    return {
        "similarity_indicator": min(similarity, 100), "queries_checked": len(chunks),
        "tavily_requests_used": len(chunks), "tavily_request_limit": TAVILY_QUERY_BUDGET,
        "queries_with_results": len(found_queries), "sources": source_list[:30],
        "match_groups": groups,
        "source_categories": {"internet_sources": len(source_list), "publications": 0, "submitted_works": 0},
        "integrity_flags": {"non_latin_lookalikes": foreign_lookalikes},
    }


def hex_to_rgb(color: str) -> tuple[float, float, float]:
    color = color.lstrip("#")
    return tuple(int(color[index:index + 2], 16) / 255 for index in (0, 2, 4))


# Put the source number in the page margin, aligned to its first highlight.
def add_source_badge(page: fitz.Page, rank: int, color: str, y: float) -> None:
    radius = 12
    center = fitz.Point(page.rect.x0 + radius + 4, max(page.rect.y0 + radius + 3, min(y, page.rect.y1 - radius - 3)))
    shape = page.new_shape()
    shape.draw_circle(center, radius)
    shape.finish(color=hex_to_rgb(color), fill=hex_to_rgb(color), width=0)
    shape.commit(overlay=True)
    label = str(rank)
    page.insert_text(fitz.Point(center.x - (3 if len(label) == 1 else 6), center.y + 4),label, fontname="hebo", fontsize=10, color=(1, 1, 1), overlay=True,)


def match_rectangles(page: fitz.Page, query: str) -> list[fitz.Rect]:
    exact = page.search_for(query, quads=False) if len(query) >= 20 else []
    if exact:
        return exact
    
    words = query.split()
    for word_count in (min(9, len(words)), 7, 5):
        phrase = " ".join(words[:word_count])

        if len(phrase) >= 20:
            rects = page.search_for(phrase, quads=False)

            if rects:
                return rects
    return []


# Keep only sources that can be tied to a position in the submitted PDF
def sources_with_locatable_text(pdf_path: Path, source_list: list[dict[str, Any]], permitted_pages: set[int]) -> list[dict[str, Any]]:
    doc = fitz.open(pdf_path)
    located: list[dict[str, Any]] = []
    for source in source_list:
        if any(match_rectangles(page, match["query"]) for page_index, page in enumerate(doc) if page_index in permitted_pages for match in source.get("matches", [])):
            located.append(source)

    doc.close()
    for rank, source in enumerate(located, 1):
        source["rank"] = rank
        source["highlight_color"] = SOURCE_COLORS[(rank - 1) % len(SOURCE_COLORS)]

    return located


def mark_pages(pdf_path: Path, sources: list[dict[str, Any]], permitted_pages: set[int], output: Path) -> int:
    doc = fitz.open(pdf_path)
    count = 0
    used_rectangles: set[tuple[int, int, int, int, int]] = set()
    source_badge_pages: dict[int, set[int]] = {}

    for page_index, page in enumerate(doc):
        if page_index not in permitted_pages:
            continue

        for source_index, source in enumerate(sources, 1):
            color = source.get("highlight_color", SOURCE_COLORS[(source_index - 1) % len(SOURCE_COLORS)])
            rgb = hex_to_rgb(color)

            for match in source.get("matches", []):
                passage = match.get("passage", match["query"])
                rects = match_rectangles(page, passage)

                for rect in rects:
                    key = (page_index, round(rect.x0), round(rect.y0), round(rect.x1), round(rect.y1))
                    if key in used_rectangles:
                        continue

                    used_rectangles.add(key)
                    annot = page.add_highlight_annot(rect)
                    annot.set_colors(stroke=rgb)
                    annot.set_opacity(0.18)
                    annot.set_info(
                        title=f"Source {source_index}: {source.get('domain', 'candidate source')}",
                        content=(
                            f"Source URL: {source.get('url', '')}\n\n"
                            f"Matched submitted passage:\n{passage}"
                        ),
                    )
                    annot.update()
                    count += 1
                    badge_pages = source_badge_pages.setdefault(source_index, set())

                    if page_index not in badge_pages:
                        add_source_badge(page, source_index, color, rect.y0)
                        badge_pages.add(page_index)

    doc.save(output, garbage=4, deflate=True)
    doc.close()
    return count


def escape_html(value: Any) -> str:
    import html
    return html.escape(str(value or ""))


def make_report(result: dict[str, Any], filename: str, output: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], alignment=0, fontName="Helvetica-Bold", fontSize=25, leading=29, textColor=colors.HexColor("#222222")))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8, leading=11, wordWrap="CJK"))
    styles.add(ParagraphStyle(name="SummaryLabel", parent=styles["BodyText"], fontSize=10, leading=13, textColor=colors.HexColor("#222222")))
    styles.add(ParagraphStyle(name="SummaryDetail", parent=styles["BodyText"], fontSize=9, leading=12, textColor=colors.HexColor("#666666")))
    groups = result["match_groups"]
    total = result["queries_checked"] or 1

    def group_line(color: str, label: str, value: int, detail: str) -> Paragraph:
        return Paragraph(
            f'<font color="{color}">●</font>&nbsp;&nbsp;<b>{value}</b> {escape_html(label)} &nbsp; {round(100 * value / total)}%'
            f'<br/><font color="#666666">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{escape_html(detail)}</font>',
            styles["SummaryLabel"],
        )

    story = [Paragraph(f"{result['similarity_indicator']}% Overall Similarity", styles["ReportTitle"]), Spacer(1, 2*mm),
             Paragraph("The share of sampled passages that produced one or more candidate web results.", styles["BodyText"]), Spacer(1, 5*mm),
             Paragraph(f"<b>Document:</b> {escape_html(filename)}", styles["BodyText"]),
             Paragraph(f"<b>Generated:</b> {escape_html(result['created_at'])} UTC", styles["BodyText"]), Spacer(1, 5*mm),
             Paragraph("Match Groups", styles["Heading2"])]
    
    match_rows = []
    for color, label, value, detail in [
        ("#e94e5f", "Uncited and unquoted", groups["uncited_unquoted"], "Candidate passages with neither a nearby citation nor quotation marks."),
        ("#f28c3a", "Quoted without citation", groups["quoted_without_citation"], "Candidate passages with quotation marks but no nearby citation pattern."),
        ("#f1c75b", "Cited without quotation marks", groups["cited_without_quotes"], "Candidate passages with a nearby citation pattern but no quotation marks."),
        ("#58b9a7", "Cited and quoted", groups["cited_and_quoted"], "Candidate passages with both a nearby citation pattern and quotation marks."),
    ]:
        
        match_rows.append([group_line(color, label, value, detail)])
    top_sources = [
        ["Internet pages", str(result["source_categories"]["internet_sources"])],
        ["Publication matches", str(result["source_categories"]["publications"])],
        ["Submitted works", "Not searched"],
    ]

    top_sources.insert(0, ["Top Sources", "Candidate pages"])
    side = Table(top_sources, colWidths=[38*mm, 28*mm], hAlign="LEFT")
    side.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#edf3f6")), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("GRID",(0,0),(-1,-1),.25,colors.HexColor("#d4dde1")), ("PADDING",(0,0),(-1,-1),5), ("VALIGN",(0,0),(-1,-1),"TOP")]))
    left = Table(match_rows, colWidths=[102*mm])
    left.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING",(0,0),(-1,-1),0), ("RIGHTPADDING",(0,0),(-1,-1),1), ("TOPPADDING",(0,0),(-1,-1),2), ("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    
    # Keep both summary panels inside the usable A4 page width (174 mm with these margins).
    overview = Table([[left, side]], colWidths=[106*mm, 66*mm])
    overview.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING",(0,0),(-1,-1),0), ("RIGHTPADDING",(0,0),(-1,-1),0), ("TOPPADDING",(0,0),(-1,-1),0), ("BOTTOMPADDING",(0,0),(-1,-1),0)]))
    flags = result["integrity_flags"]
    flag_text = "No character lookalikes were found in extracted text."
    
    if flags["non_latin_lookalikes"]:
        flag_text = f"{flags['non_latin_lookalikes']} Cyrillic or Greek character(s) were found. Review them in context; these can be valid language characters."
    
    story += [overview, Spacer(1, 5*mm), Paragraph("Document Integrity Flags", styles["Heading2"]),
              Paragraph(f"<b>Character review:</b> {flag_text}", styles["BodyText"]), Spacer(1, 4*mm),
              Paragraph("Top Sources", styles["Heading2"])]
    
    if not result["sources"]:
        story.append(Paragraph("No candidate sources were returned for the sampled passages.", styles["BodyText"]))
    
    rank_colors = ["#c91675", "#2764c6", "#00804c", "#7333e6", "#d21173"]

    for index, source in enumerate(result["sources"], 1):
        color = rank_colors[(index - 1) % len(rank_colors)]
        type_text = escape_html(source.get("source_type", "Internet"))
        domain = escape_html(source.get("domain") or urlparse(source["url"]).netloc)
        percentage = source.get("match_percentage", 0)
        percent_text = "&lt;1%" if 0 < percentage < 1 else f"{percentage:g}%"
        left = Paragraph(f'<font color="{color}"><b>{index}</b></font>&nbsp;&nbsp; <b>{type_text}</b><br/><br/><b>{domain}</b><br/><font color="#666666">{escape_html(source["title"][:115])}</font>', styles["Small"])
        right = Paragraph(f"<b>{percent_text}</b>", styles["Small"])
        row = Table([[left, right]], colWidths=[132*mm, 30*mm])
        row.setStyle(TableStyle([("BACKGROUND", (0,0), (0,0), colors.HexColor("#f7f7f7")), ("LINEBELOW",(0,0),(-1,-1),.4,colors.HexColor("#cfd5d8")), ("VALIGN",(0,0),(-1,-1),"TOP"), ("PADDING",(0,0),(-1,-1),7)]))
        story += [row, Spacer(1, 2*mm)]
        
    SimpleDocTemplate(str(output), pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=16*mm, bottomMargin=16*mm, title="Document Similarity Analysis").build(story)


def merge_pdfs(paths: list[Path], output: Path) -> None:
    merged = fitz.open()
    for path in paths:
        part = fitz.open(path)
        merged.insert_pdf(part)
        part.close()
    merged.save(output, garbage=4, deflate=True)
    merged.close()

