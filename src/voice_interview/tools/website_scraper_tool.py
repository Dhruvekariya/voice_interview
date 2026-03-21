#!/usr/bin/env python3
"""
Website Scraper Tool for CrewAI

This tool implements the functionality from the original llms.txt generator script
as a CrewAI tool that can be used by agents to scrape and analyze entire websites.

Based on the reference implementation with proper error handling and best practices.
"""

import os
import json
import time
import logging
import requests
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebsiteScraperInput(BaseModel):
    """Input schema for WebsiteScraperTool."""
    url: str = Field(..., description="The website URL to scrape and analyze")
    max_urls: int = Field(default=20, description="Maximum number of URLs to process (default: 20)")
    show_full_text: bool = Field(default=True, description="Whether to include full content in the output")

class WebsiteScraperTool(BaseTool):
    """
    Website Scraper and Analyzer Tool for CrewAI
    
    This tool replicates the functionality of the original llms.txt generator script,
    allowing CrewAI agents to scrape entire websites and analyze their content.
    
    Features:
    1. Maps all URLs from a website using Firecrawl's /map endpoint
    2. Scrapes each URL to get content in markdown format  
    3. Uses OpenAI to generate titles and descriptions
    4. Creates llms.txt and llms-full.txt style output
    5. Follows web scraping best practices from ScrapeHero guidelines
    """
    
    name: str = "Website Scraper and Analyzer"
    description: str = (
        "Scrapes and analyzes entire websites to generate comprehensive content analysis. "
        "Given a website URL, this tool will find all URLs on the website, scrape content "
        "from each page in markdown format, generate titles and descriptions, and return "
        "a structured analysis perfect for LLM consumption. Uses proper rate limiting, "
        "error handling, and follows web scraping best practices."
    )
    args_schema: type[BaseModel] = WebsiteScraperInput
    
    # Declare fields to avoid Pydantic validation errors
    firecrawl_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    delay_between_requests: float = 1.0
    max_concurrent_requests: int = 3
    openai_client: Optional[object] = None

    def __init__(self, **kwargs):
        """Initialize the tool with API keys and rate limiting."""
        super().__init__(**kwargs)
        
        # Initialize API keys and settings
        object.__setattr__(self, 'firecrawl_api_key', os.getenv("FIRECRAWL_API_KEY"))
        object.__setattr__(self, 'openai_api_key', os.getenv("OPENAI_API_KEY"))
        object.__setattr__(self, 'delay_between_requests', 1.0)
        object.__setattr__(self, 'max_concurrent_requests', 3)
        
        # Set up OpenAI client if available
        openai_client = None
        if self.openai_api_key:
            try:
                from openai import OpenAI
                openai_client = OpenAI(api_key=self.openai_api_key)
            except ImportError:
                logger.warning("OpenAI library not available for enhanced descriptions")
        
        object.__setattr__(self, 'openai_client', openai_client)

    def _run(self, url: str, max_urls: int = 20, show_full_text: bool = True) -> str:
        """
        Execute the website scraping and analysis following the reference implementation.
        
        Args:
            url: The website URL to analyze
            max_urls: Maximum number of URLs to process
            show_full_text: Whether to include full content
        
        Returns:
            Formatted llms.txt style analysis of the website content
        """
        if not self.firecrawl_api_key:
            return "❌ FIRECRAWL_API_KEY not found in environment variables. Please set it to use this tool."
        
        try:
            logger.info(f"🚀 Starting website analysis for: {url}")
            
            # Step 1: Map the website to get all URLs
            urls = self._map_website(url, max_urls)
            if not urls:
                return f"❌ Failed to map website: {url}. Please check if the URL is accessible."
            
            logger.info(f"📋 Found {len(urls)} URLs to analyze")
            
            # Step 2: Scrape content from each URL with proper rate limiting
            scraped_data = self._scrape_urls_batch(urls)
            
            if not scraped_data:
                return f"❌ No content could be scraped from: {url}. Website may be blocking requests."
            
            logger.info(f"✅ Successfully scraped {len(scraped_data)} pages")
            
            # Step 3: Generate llms.txt style output
            result = self._generate_llmstxt_output(scraped_data, url, show_full_text)
            
            logger.info(f"🎉 Analysis complete for {url}")
            return result
            
        except Exception as e:
            error_msg = f"Error analyzing website {url}: {str(e)}"
            logger.error(error_msg)
            return f"❌ {error_msg}"

    def _map_website(self, url: str, limit: int) -> List[str]:
        """Map a website to get all URLs using Firecrawl /map endpoint."""
        try:
            logger.info(f"🗺️ Mapping website: {url}")
            
            response = requests.post(
                "https://api.firecrawl.dev/v1/map",
                headers={
                    "Authorization": f"Bearer {self.firecrawl_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "url": url,
                    "limit": limit,
                    "includeSubdomains": False,
                    "ignoreSitemap": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("links"):
                    urls = data["links"][:limit]
                    logger.info(f"Successfully mapped {len(urls)} URLs")
                    return urls
                else:
                    logger.error(f"Mapping failed: {data.get('error', 'Unknown error')}")
                    return []
            else:
                logger.error(f"Mapping request failed with status {response.status_code}: {response.text}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during mapping: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error during mapping: {e}")
            return []

    def _scrape_urls_batch(self, urls: List[str]) -> List[Dict]:
        """Scrape multiple URLs with proper batching and rate limiting."""
        scraped_data = []
        
        # Process URLs in small batches to respect rate limits
        batch_size = 5
        total_batches = (len(urls) + batch_size - 1) // batch_size
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(urls))
            batch = urls[start_idx:end_idx]
            
            logger.info(f"Processing batch {batch_num + 1}/{total_batches}")
            
            # Process batch with limited concurrency
            with ThreadPoolExecutor(max_workers=self.max_concurrent_requests) as executor:
                futures = {
                    executor.submit(self._scrape_single_url, url, start_idx + j): (url, start_idx + j)
                    for j, url in enumerate(batch)
                }
                
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        if result:
                            scraped_data.append(result)
                    except Exception as e:
                        url, idx = futures[future]
                        logger.error(f"Failed to process {url}: {e}")
            
            # Respect rate limits between batches
            if batch_num < total_batches - 1:
                logger.debug(f"Waiting {self.delay_between_requests * batch_size}s before next batch...")
                time.sleep(self.delay_between_requests * batch_size)
        
        # Sort by index to maintain order
        scraped_data.sort(key=lambda x: x.get("index", 0))
        return scraped_data

    def _scrape_single_url(self, url: str, index: int) -> Optional[Dict]:
        """Scrape a single URL using Firecrawl /scrape endpoint."""
        try:
            logger.debug(f"🔍 Scraping URL {index + 1}: {url}")
            
            # Add delay to respect rate limits
            time.sleep(self.delay_between_requests)
            
            response = requests.post(
                "https://api.firecrawl.dev/v1/scrape",
                headers={
                    "Authorization": f"Bearer {self.firecrawl_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "url": url,
                    "formats": ["markdown"],
                    "onlyMainContent": True,
                    "timeout": 30000
                },
                timeout=35
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("data"):
                    content_data = data["data"]
                    markdown = content_data.get("markdown", "")
                    metadata = content_data.get("metadata", {})
                    
                    if not markdown:
                        logger.warning(f"No markdown content found for {url}")
                        return None
                    
                    # Generate title and description
                    title, description = self._generate_title_and_description(url, markdown, metadata)
                    
                    return {
                        "url": url,
                        "title": title,
                        "description": description,
                        "markdown": markdown,
                        "metadata": metadata,
                        "index": index
                    }
                else:
                    logger.error(f"Scraping failed for {url}: {data.get('error', 'Unknown error')}")
                    return None
            else:
                logger.error(f"Scraping request failed for {url} with status {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error scraping {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error scraping {url}: {e}")
            return None

    def _generate_title_and_description(self, url: str, markdown: str, metadata: Dict) -> Tuple[str, str]:
        """Generate title and description using OpenAI or fallback methods."""
        # Extract title - try metadata first, then markdown, then URL
        title = metadata.get('title', '')
        if not title:
            lines = markdown.split('\n')
            for line in lines:
                if line.startswith('# '):
                    title = line[2:].strip()
                    break
        
        if not title:
            # Generate from URL path
            path = urlparse(url).path
            title = path.replace('/', ' ').replace('-', ' ').replace('_', ' ').strip()
            if not title or title == ' ':
                title = "Homepage"
            title = title.title()
        
        # Limit title length
        if len(title) > 60:
            title = title[:57] + "..."
        
        # Generate description using OpenAI
        description = self._generate_ai_description(url, markdown)
        
        # Fallback to metadata description
        if not description:
            description = metadata.get('description', '')
        
        # Fallback to first paragraph
        if not description:
            paragraphs = [p.strip() for p in markdown.split('\n\n') if p.strip() and not p.startswith('#')]
            if paragraphs:
                first_para = paragraphs[0]
                if len(first_para) > 150:
                    description = first_para[:147] + "..."
                else:
                    description = first_para
            else:
                description = f"Content from {urlparse(url).netloc}"
        
        return title, description

    def _generate_ai_description(self, url: str, markdown: str) -> str:
        """Generate AI-powered description using OpenAI."""
        if not self.openai_client:
            return ""
        
        try:
            # Limit content length for API efficiency
            content_preview = markdown[:2000] if len(markdown) > 2000 else markdown
            
            prompt = f"""Generate a concise 8-12 word description of this webpage content. Focus on the main purpose and key information.

URL: {url}
Content: {content_preview}

Respond with just the description, no quotes or extra text."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that creates concise webpage descriptions. Always respond with just the description text, no quotes or formatting."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.3
            )
            
            description = response.choices[0].message.content.strip()
            # Remove quotes if present
            if description.startswith('"') and description.endswith('"'):
                description = description[1:-1]
            
            return description
            
        except Exception as e:
            logger.error(f"Failed to generate AI description for {url}: {e}")
            return ""

    def _generate_llmstxt_output(self, scraped_data: List[Dict], base_url: str, show_full_text: bool) -> str:
        """Generate llms.txt and llms-full.txt style output following the reference format."""
        domain = urlparse(base_url).netloc.replace("www.", "")
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        
        # Build the llms.txt content (page directory)
        llmstxt_content = ""
        for page in scraped_data:
            llmstxt_content += f"- [{page['title']}]({page['url']}): {page['description']}\n"
        
        # Build the llms-full.txt content (complete content)
        llms_fulltxt_content = ""
        for i, page in enumerate(scraped_data, 1):
            llms_fulltxt_content += f"<|firecrawl-page-{i}-lllmstxt|>\n"
            llms_fulltxt_content += f"## {page['title']}\n"
            llms_fulltxt_content += f"{page['markdown']}\n\n"
        
        # Format final output
        if show_full_text:
            output = f"""# 🌐 Website Analysis: {domain}

**📊 Analysis Summary**
- **Total Pages Analyzed**: {len(scraped_data)}
- **Analysis Date**: {timestamp}
- **Full Content Included**: Yes

## 📋 llms.txt - Page Directory

# {domain} llms.txt

{llmstxt_content}

## 📄 llms-full.txt - Complete Content

# {domain} llms-full.txt

{llms_fulltxt_content}

## 🎯 Analysis Complete

✅ Successfully analyzed {len(scraped_data)} pages
✅ Content optimized for LLM processing  
✅ Ready for AI analysis and insight generation
✅ Rate limiting and best practices followed

*Generated using Website Scraper Tool for CrewAI*
"""
        else:
            output = f"""# 🌐 Website Analysis: {domain}

**📊 Analysis Summary**
- **Total Pages Analyzed**: {len(scraped_data)}
- **Analysis Date**: {timestamp}
- **Full Content Included**: No (Directory Only)

## 📋 llms.txt - Page Directory

# {domain} llms.txt

{llmstxt_content}

✅ Page directory generated successfully
💡 Use show_full_text=True to include complete content
✅ Rate limiting and best practices followed

*Generated using Website Scraper Tool for CrewAI*
"""
        
        return output 