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
    
    def search_similar(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for similar documents to the query."""
        try:
            # Generate embedding for the query
            query_embedding = self.embedding_model.encode(
                query,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True
            ).tolist()
            
            # Search in Qdrant
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=limit,
                with_vectors=False,
                with_payload=True
            )
            
            # Format results
            return [
                {
                    'id': str(hit.id),
                    'score': hit.score,
                    'text': hit.payload.get('text', ''),
                    'metadata': {
                        k: v for k, v in hit.payload.items()
                        if k != 'text'
                    }
                }
                for hit in search_results
            ]
            
        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}")
            raise
    
    def clear_collection(self) -> bool:
        """Clear all vectors from the collection."""
        try:
            self.client.delete_collection(collection_name=self.collection_name)
            self._ensure_collection()  # Recreate the collection
            return True
        except Exception as e:
            logger.error(f"Error clearing collection: {str(e)}")
            return False
