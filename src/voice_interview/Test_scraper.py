#!/usr/bin/env python3
"""
Test script for the Website Scraper Tool
"""

import sys
import os

# Add the project root to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from src.voice_interview.tools.website_scraper_tool import WebsiteScraperTool

def test_firecrawl_scraping():
    """Test scraping firecrawl.dev website"""
    
    print("🚀 Testing Website Scraper Tool")
    print("=" * 50)
    
    # Initialize the tool
    scraper = WebsiteScraperTool()
    
    # Test with Firecrawl's own website
    url = "https://www.firecrawl.dev/"
    max_urls = 10  # Start small for testing
    
    print(f"📋 Testing URL: {url}")
    print(f"📊 Max URLs to scrape: {max_urls}")
    print("⏳ Starting scrape...\n")
    
    try:
        # Run the scraper
        result = scraper._run(
            url=url,
            max_urls=max_urls,
            show_full_text=True  # Set to False for just the directory
        )
        
        print("✅ Scraping completed!")
        print("=" * 50)
        print(result)
        
        # Save results to file
        output_file = os.path.join(os.path.dirname(__file__), "../../firecrawl_analysis.md")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result)
        
        print(f"\n💾 Results saved to: {output_file}")
        
    except Exception as e:
        print(f"❌ Error during scraping: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def test_directory_only():
    """Test with directory only (no full content)"""
    
    print("\n" + "=" * 50)
    print("🧪 Testing Directory-Only Mode")
    print("=" * 50)
    
    scraper = WebsiteScraperTool()
    
    result = scraper._run(
        url="https://www.firecrawl.dev/",
        max_urls=5,
        show_full_text=False  # Directory only
    )
    
    print(result)
    
    # Save directory-only results
    output_file = os.path.join(os.path.dirname(__file__), "../../firecrawl_directory.md")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(result)
    
    print(f"\n💾 Directory saved to: {output_file}")

if __name__ == "__main__":
    # Test full scraping
    success = test_firecrawl_scraping()
    
    if success:
        # Test directory-only mode
        test_directory_only()
        
        print("\n🎉 All tests completed!")
        print("📁 Check the generated .md files for results")
    else:
        print("\n❌ Tests failed - check your API key and internet connection")