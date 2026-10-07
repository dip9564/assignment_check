import os
import re
import fitz  
from difflib import SequenceMatcher


def clear_highlighted_files():
    highlight_dir = "uploads/highlighted"

    if not os.path.exists(highlight_dir):
        return

    for filename in os.listdir(highlight_dir):
        file_path = os.path.join(highlight_dir,filename)

        if os.path.isfile(file_path):
            os.remove(file_path)


def get_matching_blocks(text1, text2, min_words=6):

    words1 = re.findall(r"\b\w+\b", text1.lower())
    words2 = re.findall(r"\b\w+\b", text2.lower())

    matcher = SequenceMatcher(None,words1,words2,autojunk=False)

    blocks = []

    for block in matcher.get_matching_blocks():
        start1, start2, size = block
        if size >= min_words:
            blocks.append({
                "start1": start1,
                "start2": start2,
                "size": size
            })

    return blocks


def create_highlight(document, words):

    if not words:
        return

    page_number = words[0]["page"]

    x0 = min(word["x0"] for word in words)
    y0 = min(word["y0"] for word in words)

    x1 = max(word["x1"] for word in words)
    y1 = max(word["y1"] for word in words)

    rect = fitz.Rect(x0,y0,x1,y1)
    page = document[page_number]
    highlight = page.add_highlight_annot(rect)

    highlight.update()
    

def highlight_pdf(pdf_path,words,matching_indices,output_path):

    document = fitz.open(pdf_path)

    # Group matching words by page and line
    line_groups = {}
    for index in matching_indices:
        word = words[index]
        key = (word["page"],word["block"],word["line"])

        if key not in line_groups:
            line_groups[key] = []

        line_groups[key].append(word)

    # Create highlights
    for key, line_words in line_groups.items():
        line_words.sort(key=lambda word: word["word_no"])

        # Split distant words on same line
        current_group = [line_words[0]]

        for word in line_words[1:]:
            previous = current_group[-1]
            gap = word["x0"] - previous["x1"]

            if gap <= 25:
                current_group.append(word)

            else:
                create_highlight(document,current_group)
                current_group = [word]

        # Last group
        if current_group:
            create_highlight(document,current_group)

    document.save(output_path)
    document.close()


def get_pdf_words(file_path, skip_pages=0):
    document = fitz.open(file_path)
    all_words = []

    for page_number in range(skip_pages, len(document)):
        page = document[page_number]
        words = page.get_text("words")

        for word in words:
            clean_word = re.sub(r"[^\w]","",word[4].lower())

            if not clean_word:
                continue

            all_words.append({
                "text": clean_word,
                "page": page_number,
                "x0": word[0],
                "y0": word[1],
                "x1": word[2],
                "y1": word[3],
                "block": word[5],
                "line": word[6],
                "word_no": word[7]
            })

    document.close()
    return all_words


def get_matching_blocks_from_words(words1, words2, min_words=6):

    sequence1 = [word["text"] for word in words1]
    sequence2 = [word["text"] for word in words2]

    matcher = SequenceMatcher(None,sequence1,sequence2,autojunk=False)

    blocks = []
    for start1, start2, size in matcher.get_matching_blocks():
        if size >= min_words:
            blocks.append({
                "start1": start1,
                "start2": start2,
                "size": size
            })

    return blocks


def get_highlights(student1_pdf, student2_pdf):

    # Remove previous highlighted PDFs
    clear_highlighted_files()

    # Extract words + PDF coordinates
    words1 = get_pdf_words(student1_pdf,skip_pages=0)
    words2 = get_pdf_words(student2_pdf,skip_pages=0)

    if not words1 or not words2:
        return {
            "message": "Could not extract enough text",
            "student1": student1_pdf,
            "student2": student2_pdf
        }

    # Find long matching sequences
    matching_blocks = get_matching_blocks_from_words(words1, words2, min_words=6)

    if not matching_blocks:
        return {
            "message": "No meaningful matching passages found",
            "student1": student1_pdf,
            "student2": student2_pdf
        }

    # Get matching word indices
    matched_indices1 = set()
    matched_indices2 = set()

    for block in matching_blocks:
        start1 = block["start1"]
        start2 = block["start2"]
        size = block["size"]

        for i in range(size):
            matched_indices1.add(start1 + i)
            matched_indices2.add(start2 + i)


    # Create output directory
    highlight_dir = "uploads/highlighted"
    
    os.makedirs(highlight_dir, exist_ok=True)
    
    output1 = os.path.join(
        highlight_dir,
        os.path.basename(student1_pdf)
    )
    
    output2 = os.path.join(
        highlight_dir,
        os.path.basename(student2_pdf)
    )
    
    highlight_pdf(
        student1_pdf,
        words1,
        matched_indices1,
        output1
    )
    
    highlight_pdf(
        student2_pdf,
        words2,
        matched_indices2,
        output2
    )

    return {
    "message": "Highlighted PDFs generated",
    "student1_pdf": os.path.basename(output1),
    "student2_pdf": os.path.basename(output2),
    "matching_blocks": len(matching_blocks),
    "matched_words_student1": len(matched_indices1),
    "matched_words_student2": len(matched_indices2)
}
