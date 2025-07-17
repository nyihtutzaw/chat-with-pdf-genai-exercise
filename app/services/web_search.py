import asyncio
import logging
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor
from duckduckgo_search import DDGS
import requests

logger = logging.getLogger(__name__)

class WebSearchService:
    def __init__(self, max_results: int = 5):
        self.max_results = max_results

    async def search(self, query: str, region: str = 'us-en', time_period: str = None) -> List[Dict[str, str]]:
        """
        Perform an asynchronous web search using DuckDuckGo.
        
        Args:
            query: The search query
            region: Region code (e.g., 'wt-wt' for worldwide, 'us-en' for US English)
            time_period: Time period for results (e.g., 'd' for day, 'w' for week, 'm' for month)
            
        Returns:
            List of search results with title, link, and snippet
        """
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as pool:
            return await loop.run_in_executor(
                pool, 
                lambda: self._sync_search(query, region, time_period)
            )
            
    def _sync_search(self, query: str, region: str = 'us-en', time_period: str = None) -> List[Dict[str, str]]:
        """
        Perform a web search using DuckDuckGo.
        
        Args:
            query: The search query
            region: Region code (e.g., 'us-en' for US English)
            time_period: Time period for results (e.g., 'd' for day, 'w' for week, 'm' for month)
            
        Returns:
            List of search results with title, link, and snippet
        """
        try:
            logger.info("Performing web search for: %s", query)
            
            with DDGS() as ddgs:
                results = list(ddgs.text(
                    query,
                    region=region,
                    timelimit=time_period,
                    max_results=self.max_results,
                    safesearch='moderate'
                ))
            
            if not results:
                logger.warning("No results found for query: %s", query)
                return []
                
            # Format results
            formatted_results = []
            seen_links = set()
            
            for result in results:
                link = result.get('href', '')
                if not link or link in seen_links:
                    continue
                    
                formatted_results.append({
                    'title': result.get('title', 'No title'),
                    'link': link,
                    'snippet': result.get('body', 'No description available'),
                    'source': 'web_search'
                })
                seen_links.add(link)
                
                if len(formatted_results) >= self.max_results:
                    break
            
            logger.info("Found %d results", len(formatted_results))
            return formatted_results
            
        except requests.RequestException as e:
            logger.error("Network error during web search: %s", str(e), exc_info=True)
        except Exception as e:
            logger.error("Unexpected error during web search: %s", str(e), exc_info=True)
            
        return []
        
    @staticmethod
    def _clean_query(query: str) -> str:
        """Clean and enhance the search query."""
        # Remove common non-essential words that might confuse the search
        stop_words = {'what', 'who', 'where', 'when', 'why', 'how', 'do', 'does', 'is', 'are', 'the', 'a', 'an', 'and', 'or', 'in', 'on', 'at'}
        cleaned = ' '.join([word for word in query.split() if word.lower() not in stop_words])
        return cleaned.strip()
        
    def _is_high_quality_result(self, title: str, snippet: str) -> bool:
        """Check if a search result is high quality and relevant."""
        # Basic validation
        if not title or not snippet:
            return False
            
        # Simple length check
        if len(title) < 5 or len(snippet) < 10:
            return False
            
        return True
    
    @staticmethod
    def _is_english(text: str, threshold: float = 0.8) -> bool:
        """Check if text is primarily English."""
        if not text.strip():
            return False
            
        # Simple check for non-ASCII characters
        try:
            text.encode('ascii')
            return True
        except UnicodeEncodeError:
            # Count English alphabet characters vs others
            english_chars = sum(1 for c in text if 'a' <= c.lower() <= 'z' or c.isspace())
            return (english_chars / len(text)) > threshold
            
    def _calculate_relevance(self, query: str, title: str, snippet: str) -> float:
        """Calculate relevance score of a search result."""
        if not query or not title or not snippet:
            return 0.0
            
        # Simple keyword matching for now
        query_terms = set(query.lower().split())
        text = f"{title} {snippet}".lower()
        
        # Count matching terms
        matches = sum(1 for term in query_terms if term in text)
        
        # Give more weight to title matches
        title_matches = sum(1 for term in query_terms if term in title.lower())
        
        # Calculate score (0.0 to 1.0)
        score = (matches * 0.3) + (title_matches * 0.7)
        return min(1.0, score / len(query_terms) if query_terms else 0.0)

# Create a singleton instance
web_search_service = WebSearchService()
