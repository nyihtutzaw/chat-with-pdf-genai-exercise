import asyncio
import logging
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor
from ddgs import DDGS
import requests

logger = logging.getLogger(__name__)

class WebSearchService:
    def __init__(self, max_results: int = 5):
        self.max_results = max_results

    async def search(self, query: str, region: str = 'us-en', time_period: str = None) -> List[Dict[str, str]]:
     
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as pool:
            return await loop.run_in_executor(
                pool, 
                lambda: self._sync_search(query, region, time_period)
            )
            
    def _sync_search(self, query: str, region: str = 'us-en', time_period: str = None) -> List[Dict[str, str]]:
      
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
        

web_search_service = WebSearchService()
