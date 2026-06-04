# pdf_handler.py
#
# WHAT THIS FILE DOES:
# 1. Takes a PDF file uploaded by the user
# 2. Extracts all the text from every page
# 3. Splits that text into small overlapping "chunks"
#
# WHY CHUNKS?
# A PDF might be 100 pages. We can't send all of it to the LLM at once
# (too many tokens). Instead we cut it into ~500-word pieces, store them
# in FAISS, and only send the 3-5 most relevant pieces per question.
#
# WHY OVERLAP?
# If a sentence is split across two chunks, the overlap (50 chars) ensures
# neither chunk loses context at its edges.

import pdfplumber
from langchain_text_splitters import RecursiveCharacterTextSplitter


def extract_text_from_pdf(uploaded_file) -> str:
    """
    Reads every page of the PDF and returns one big string of text.
    `uploaded_file` is the object Streamlit gives us from st.file_uploader.
    """
    full_text = ""

    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:  # some pages are images and return None
                full_text += page_text + "\n"

    return full_text


def split_text_into_chunks(text: str) -> list[str]:
    """
    Splits the full PDF text into overlapping chunks.

    chunk_size=500   → each chunk is ~500 characters
    chunk_overlap=50 → consecutive chunks share 50 characters at the border
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", ".", " "],  # try to split on natural boundaries
    )

    chunks = splitter.split_text(text)
    return chunks
