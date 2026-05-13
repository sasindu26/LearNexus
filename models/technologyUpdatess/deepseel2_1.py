import requests
from bs4 import BeautifulSoup

def fetch_devto_articles(tag=None, max_articles=60):
    """
    Fetches articles from the Dev.to API.
    
    Args:
        tag (str): Filter articles by a specific tag (e.g., "python").
        max_articles (int): Maximum number of articles to fetch.
    
    Returns:
        list: A list of dictionaries containing article data.
    """
    base_url = "https://dev.to/api/articles"
    articles = []
    page = 1

    while len(articles) < max_articles:
        # Add query parameters (tag and pagination)
        params = {"page": page}
        if tag:
            params["tag"] = tag

        # Fetch articles from the API
        response = requests.get(base_url, params=params)
        if response.status_code != 200:
            print(f"Error: Unable to fetch articles (Status Code: {response.status_code})")
            break

        # Parse the JSON response
        new_articles = response.json()
        if not new_articles:
            break  # No more articles to fetch

        # Extract relevant fields from each article
        for article in new_articles:
            article_data = {
                "title": article.get("title", ""),
                "description": article.get("description", ""),
                "url": article.get("url", ""),
                "tags": article.get("tag_list", []),
                "published_at": article.get("published_at", ""),
                "full_description": scrape_full_description(article.get("url", ""))  # Scrape full content
            }
            articles.append(article_data)

            if len(articles) >= max_articles:
                break

        page += 1

    return articles

def scrape_full_description(article_url):
    """
    Scrapes the full description/content of an article from its URL.
    
    Args:
        article_url (str): The URL of the article.
    
    Returns:
        str: The full description/content of the article.
    """
    response = requests.get(article_url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        # Find the article content (adjust the selector as needed)
        content = soup.find("div", class_="crayons-article__main")
        if content:
            return content.get_text(strip=True)
    return ""

def save_articles_to_file(articles, filename="devto_articles_7.json"):
    """
    Saves the extracted articles to a JSON file.
    
    Args:
        articles (list): List of article data.
        filename (str): Name of the output file.
    """
    import json
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(articles, file, indent=4)
    print(f"Saved {len(articles)} articles to {filename}")


def main():
    # Fetch articles (e.g., tagged with "python")
    # Fetch for many tags and aggregate results
    tags = ["python", "javascript", "devops", "machine-learning", "react", "docker"]  # adjust list as needed
    per_tag_max = 10  # number of articles to fetch per tag (adjust as needed)

    # Collect articles for all tags, deduplicate by URL
    collected_articles = []
    seen_urls = set()
    
    for t in tags:
        for art in fetch_devto_articles(tag=t, max_articles=per_tag_max):
            if art.get("url") and art["url"] not in seen_urls:
                seen_urls.add(art["url"])
                collected_articles.append(art)

    # Use the collected articles directly
    articles = collected_articles[:50]  # Limit to 50 articles

    # Print the first 5 articles as a sample
    for i, article in enumerate(articles[:5]):
        print(f"Article {i + 1}:")
        print(f"  Title: {article['title']}")
        print(f"  Description: {article['description']}")
        print(f"  Full Description: {article['full_description'][:200]}...")  # Preview first 200 chars
        print(f"  URL: {article['url']}")
        print(f"  Tags: {', '.join(article['tags'])}")
        print(f"  Published At: {article['published_at']}")
        print()

    # Save all articles to a JSON file
    save_articles_to_file(articles)

    
if __name__ == "__main__":
    main()