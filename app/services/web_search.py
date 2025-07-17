import asyncio
import logging
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

class WebSearchService:
    def __init__(self, max_results: int = 5):
        self.max_results = max_results

    async def search(self, query: str, region: str = 'wt-wt', time_period: str = None) -> List[Dict[str, str]]:
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
            
    def _sync_search(self, query: str, region: str, time_period: str) -> List[Dict[str, str]]:
        """
        Perform a web search using DuckDuckGo.
        
        Args:
            query: The search query
            region: Region code (e.g., 'wt-wt' for worldwide, 'us-en' for US English)
            time_period: Time period for results (e.g., 'd' for day, 'w' for week, 'm' for month)
            
        Returns:
            List of search results with title, link, and snippet
        """
        try:
            logger.info(f"Performing web search for: {query}")
            with DDGS() as ddgs:
                results = list(ddgs.text(
                    query,
                    region=region,
                    timelimit=time_period,
                    max_results=self.max_results
                ))
            
            if not results:
                logger.warning(f"No results found for query: {query}")
                return []
                
            # Format results to match our expected format
            formatted_results = []
            for result in results[:self.max_results]:
                formatted_results.append({
                    'title': result.get('title', 'No title'),
                    'link': result.get('href', ''),
                    'snippet': result.get('body', 'No description available'),
                    'source': 'web_search'
                })
                
            logger.info(f"Found {len(formatted_results)} results")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error performing web search: {str(e)}")
            return []

# Create a singleton instance
web_search_service = WebSearchService()
