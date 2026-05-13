import requests

def fetch_devto_articles(tag=None, max_articles=50):
    """
    Fetches articles from the Dev.to API.
    
    Args:
        tag (str): Filter articles by a specific tag (e.g., "python").
        max_articles (int): Maximum number of articles to fetch.
    
    Returns:
        list: A list of dictionaries containing article data (title, description, url, tags).
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
                "published_at": article.get("published_at", "")
            }
            articles.append(article_data)

            if len(articles) >= max_articles:
                break

        page += 1

    return articles

def save_articles_to_file(articles, filename="devto_articles.json"):
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
    tag = "python"  # Change this to any tag you're interested in
    max_articles = 60  # Number of articles to fetch
    articles = fetch_devto_articles(tag=tag, max_articles=max_articles)
    
    print(f"\nFetched {len(articles)} articles about {tag}:\n")
    
    # Print all articles
    for i, article in enumerate(articles, 1):
        print(f"Article {i}:")
        print(f"  Title: {article['title']}")
        print(f"  Description: {article['description']}")
        print(f"  URL: {article['url']}")
        print(f"  Tags: {', '.join(article['tags'])}")
        print(f"  Published At: {article['published_at']}")
        print()
    
    # Save articles to a file in the same directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(current_dir, "devto_articles.json")
    save_articles_to_file(articles, output_file)

if __name__ == "__main__":
    import os
    main()