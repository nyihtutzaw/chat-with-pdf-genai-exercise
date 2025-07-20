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
    
    def __init__(self):
        
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
        if not documents:
            return 0
        
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

    def search_similar(self, query: str, limit: int = 5, min_similarity: float = 0.5, filter_doc_names: List[str] = None) -> List[Dict[str, Any]]:
       
        try:
            # Generate embedding for the query first
            query_embedding = self.embedding_model.encode(
                query,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True
            ).tolist()
            
            # Prepare filters if document names are provided
            filter_condition = None
            if filter_doc_names and any(name.strip() for name in filter_doc_names):
                from qdrant_client.http import models as rest
                
                # Create a list of match conditions for each document name
                match_conditions = []
                for name in filter_doc_names:
                    if not name.strip():
                        continue
                    # Normalize the document name for more flexible matching
                    normalized_name = self._normalize_document_name(name)
                    if normalized_name:
                        match_conditions.append(
                            rest.FieldCondition(
                                key="source",
                                match=rest.MatchText(text=normalized_name)
                            )
                        )
                
                if match_conditions:
                    filter_condition = rest.Filter(
                        should=match_conditions,
                        min_should_match=1
                    )
            
            # First try with the original query and filters
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=filter_condition,
                limit=limit * 2,  # Get more results for filtering
                with_vectors=False,
                with_payload=True,
                score_threshold=min_similarity
            )
            
            # If no results with filters, try without filters
            if not search_results and filter_condition:
                search_results = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=query_embedding,
                    limit=limit,
                    with_vectors=False,
                    with_payload=True,
                    score_threshold=min_similarity
                )
            
            results = []
            seen_texts = set()  
            
            for hit in search_results:
                if len(results) >= limit:
                    break
                    
                text = hit.payload.get('text', '').strip()
                if not text or text in seen_texts:
                    continue
                    
                results.append({
                    'id': str(hit.id),
                    'score': float(hit.score),
                    'text': text,
                    'metadata': {
                        k: v for k, v in hit.payload.items()
                        if k != 'text' and v is not None
                    }
                })
                seen_texts.add(text)
            
            if len(results) < limit and min_similarity > 0.5:
                additional_results = self.search_similar(
                    query=query,
                    limit=limit - len(results),
                    min_similarity=0.5, 
                    filter_doc_names=filter_doc_names
                )
                
                # Add only unique results
                for res in additional_results:
                    if res['text'] not in seen_texts:
                        results.append(res)
                        seen_texts.add(res['text'])
                        if len(results) >= limit:
                            break
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}", exc_info=True)
            try:
                search_results = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=query_embedding,
                    limit=limit,
                    with_payload=True
                )
                return [{
                    'id': str(hit.id),
                    'score': float(hit.score),
                    'text': hit.payload.get('text', ''),
                    'metadata': {k: v for k, v in hit.payload.items() if k != 'text'}
                } for hit in search_results]
            except Exception as inner_e:
                logger.error(f"Fallback search also failed: {str(inner_e)}")
                return []

vector_store = VectorStore()
