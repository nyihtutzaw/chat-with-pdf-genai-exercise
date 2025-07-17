import logging
import uuid
from typing import List, Dict, Any

from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from app.config.config import settings

logger = logging.getLogger(__name__)

class VectorStore:
    """Handles document embeddings and vector storage using Qdrant."""
    
    def __init__(self):
        """Initialize the vector store with Qdrant client and embedding model."""
        self.client = QdrantClient(url=settings.QDRANT_URL, timeout=60.0)
        self.collection_name = settings.QDRANT_COLLECTION
        self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
        self._ensure_collection()
    
    def _ensure_collection(self) -> None:
        """Ensure the Qdrant collection exists with proper configuration."""
        collections = self.client.get_collections()
        collection_names = [collection.name for collection in collections.collections]
        
        if self.collection_name not in collection_names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.embedding_model.get_sentence_embedding_dimension(),
                    distance=models.Distance.COSINE
                )
            )
            logger.info(f"Created collection: {self.collection_name}")
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of text chunks."""
        if not texts:
            return []
            
        try:
            return self.embedding_model.encode(
                texts,
                show_progress_bar=True,
                convert_to_numpy=True,
                normalize_embeddings=True
            ).tolist()
        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            raise
    
    def store_documents(self, documents: List[Dict[str, Any]]) -> int:
        """Store document chunks in the vector store with embeddings."""
        if not documents:
            return 0
        
        # Prepare data for batch upload
        points = []
        texts = [doc['text'] for doc in documents]
        embeddings = self.generate_embeddings(texts)
        
        for doc, embedding in zip(documents, embeddings):
            point_id = str(uuid.uuid4())
            # Create a copy of the doc without the text field for metadata
            metadata = {k: v for k, v in doc.items() if k != 'text'}
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        'text': doc['text'],
                        **metadata
                    }
                )
            )
        
        # Upload in batches to handle large datasets
        batch_size = 100
        total_stored = 0
        
        for i in tqdm(range(0, len(points), batch_size), desc="Uploading to vector store"):
            batch = points[i:i + batch_size]
            try:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=batch,
                    wait=True
                )
                total_stored += len(batch)
            except Exception as e:
                logger.error(f"Error uploading batch {i//batch_size + 1}: {str(e)}")
                raise
        
        return total_stored
    
    def _normalize_document_name(self, name: str) -> str:
        """Normalize document name for more flexible matching."""
        import re
        # Remove common punctuation and extra spaces
        name = re.sub(r'[^\w\s-]', ' ', name.lower())
        # Remove year patterns like (2024) or [2024]
        name = re.sub(r'\s*[\[\(]\d{4}[\]\)]', '', name)
        # Replace multiple spaces with single space
        name = re.sub(r'\s+', ' ', name).strip()
        return name

    def search_similar(self, query: str, limit: int = 5, min_similarity: float = 0.2, filter_doc_names: List[str] = None) -> List[Dict[str, Any]]:
        """
        Search for similar documents to the query.
        
        Args:
            query: The search query
            limit: Maximum number of results to return
            min_similarity: Minimum similarity score (0-1) for results to be considered relevant
            filter_doc_names: Optional list of document names to filter results by
            
        Returns:
            List of relevant documents with their scores and metadata
        """
        try:
            # Extract document names from query if not provided
            if filter_doc_names is None:
                filter_doc_names = []
                
                # Look for patterns like "in Zhang et al.(2024)" or "from DocumentName"
                import re
                doc_patterns = [
                    r'in\s+([A-Za-z0-9\s\.\-]+\s*[\(\[]?\d{4}[\)\]]?)',  # e.g., "in Zhang et al.(2024)"
                    r'from\s+([A-Za-z0-9\s\.\-]+)(?:\s+paper|document)?',  # e.g., "from DocumentName"
                    r'paper\s+["\']([^"\']+)["\']',  # e.g., "paper 'Document Name'"
                    r'([A-Z][A-Za-z]+\s+et\s+al\.?[\s\-]*(?:\(?\d{4}\))?)',  # e.g., "Zhang et al. (2024)"
                ]
                
                for pattern in doc_patterns:
                    matches = re.findall(pattern, query, re.IGNORECASE)
                    if matches:
                        # Clean up and normalize the matched document names
                        for match in matches:
                            # Remove any trailing punctuation or spaces
                            clean_name = re.sub(r'[^\w\s-]', ' ', match).strip()
                            if clean_name and clean_name not in filter_doc_names:
                                filter_doc_names.append(clean_name)
            
            # Generate embedding for the query
            query_embedding = self.embedding_model.encode(
                query,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True
            ).tolist()
            
            # Prepare filter if document names are specified
            filter_condition = None
            if filter_doc_names:
                # Normalize filter patterns for more flexible matching
                normalized_filters = [self._normalize_document_name(name) for name in filter_doc_names]
                # Create a list of patterns to match any part of the document name
                patterns = []
                for name in normalized_filters:
                    # Split into words and create a pattern that matches any word
                    words = name.split()
                    if len(words) > 2:  # For longer names, use the most significant parts
                        # Include first word + last word, or first two words if only two words
                        patterns.append(f"({words[0]}.*{words[-1]}|{' '.join(words[:2])})")
                    else:
                        patterns.append('.*'.join(words))
                
                from qdrant_client.http import models as rest
                
                # Create a list of match conditions for each pattern
                match_conditions = []
                for pattern in patterns:
                    match_conditions.append(
                        rest.FieldCondition(
                            key="source",
                            match=rest.MatchText(text=pattern)
                        )
                    )
                
                # If we have multiple conditions, combine them with OR
                if len(match_conditions) > 1:
                    filter_condition = rest.Filter(
                        should=match_conditions,
                        min_should_match=1
                    )
                else:
                    filter_condition = rest.Filter(
                        must=match_conditions
                    )
            
            # Search in Qdrant with optional filter
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=filter_condition,
                limit=limit,
                with_vectors=False,
                with_payload=True,
                score_threshold=min_similarity
            )
            
            # Format results
            results = []
            for hit in search_results:
                source = hit.payload.get('source', '').lower()
                # Skip if we have document filters and this result doesn't match any of them
                if filter_doc_names:
                    source_normalized = self._normalize_document_name(source)
                    filter_matched = any(
                        all(term in source_normalized for term in self._normalize_document_name(name).split())
                        for name in filter_doc_names
                    )
                    if not filter_matched:
                        continue
                
                results.append({
                    'id': str(hit.id),
                    'score': hit.score,
                    'text': hit.payload.get('text', ''),
                    'metadata': {
                        k: v for k, v in hit.payload.items()
                        if k != 'text'
                    }
                })
            return results
            
        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}")
            return []  # Return empty list on error
    
    def clear_collection(self) -> bool:
        """Clear all vectors from the collection."""
        try:
            self.client.delete_collection(collection_name=self.collection_name)
            self._ensure_collection()  # Recreate the collection
            return True
        except Exception as e:
            logger.error(f"Error clearing collection: {str(e)}")
            return False

    def delete_collection(self):
        """Delete the entire collection."""
        try:
            self.client.delete_collection(collection_name=self.collection_name)
            logger.info(f"Collection '{self.collection_name}' deleted successfully")
        except Exception as e:
            logger.error(f"Error deleting collection '{self.collection_name}': {str(e)}")
            raise

# Create a global instance of the VectorStore
vector_store = VectorStore()
