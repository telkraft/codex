from pathlib import Path
from typing import List, Dict
import os
from qdrant_client.models import Distance, VectorParams, PointStruct
from qdrant_client.http.exceptions import UnexpectedResponse
import uuid

async def process_document(file_path: Path, collection: str) -> List[Dict]:
    """
    Process uploaded document and index into Qdrant
    """
    from main import qdrant_client, embedding_model
    
    # Ensure collection exists
    try:
        qdrant_client.get_collection(collection)
    except UnexpectedResponse:
        # Create collection if it doesn't exist
        qdrant_client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )
    except Exception:
        # Collection exists, continue
        pass
    
    # Extract text based on file type
    file_ext = file_path.suffix.lower()
    
    if file_ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    
    elif file_ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(file_path))
        text = "\n\n".join([page.extract_text() for page in reader.pages])
    
    elif file_ext == ".docx":
        from docx import Document
        doc = Document(str(file_path))
        text = "\n\n".join([para.text for para in doc.paragraphs])
    
    else:
        raise ValueError(f"Unsupported file type: {file_ext}")
    
    # Chunk text
    chunks = chunk_text(text, max_size=512, overlap=50)
    
    # Generate embeddings and upload to Qdrant
    points = []
    for i, chunk in enumerate(chunks):
        embedding = embedding_model.encode(chunk).tolist()
        
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={
                "text": chunk,
                "metadata": {
                    "filename": file_path.name,
                    "chunk_index": i,
                    "total_chunks": len(chunks)
                }
            }
        )
        points.append(point)
    
    # Upload to Qdrant
    qdrant_client.upsert(
        collection_name=collection,
        points=points
    )
    
    return chunks

def chunk_text(text: str, max_size: int = 512, overlap: int = 50) -> List[str]:
    """
    Split text into overlapping chunks
    """
    words = text.split()
    chunks = []
    
    start = 0
    while start < len(words):
        end = start + max_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start = end - overlap
    
    return chunks
