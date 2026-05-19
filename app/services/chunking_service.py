from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List
import logging

logger = logging.getLogger("finragvault.services.chunking")


class ChunkingService:
    """Orchestrates character text splitting using LangChain splitters."""

    @staticmethod
    def split_text(text: str, chunk_size: int = 800, chunk_overlap: int = 150) -> List[str]:
        """Splits full document text into overlapping segments based on punctuation and line break bounds.
        
        Args:
            text (str): Full raw text string.
            chunk_size (int): Max character length per chunk.
            chunk_overlap (int): Overlap character length.
            
        Returns:
            List[str]: List of text chunks.
        """
        if not text or not text.strip():
            return []
            
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        
        chunks = splitter.split_text(text)
        logger.info(f"Split raw text into {len(chunks)} chunks (size: {chunk_size}, overlap: {chunk_overlap})")
        return chunks
