import requests

def fetch_dev_to_articles(tag=""):
    """
    Fetch articles from dev.to API with titles, descriptions, and URLs
    
    :param tag: Optional tag to filter articles
    """
    url = f"https://dev.to/api/articles?tag={tag}&state=rising&per_page=10"  # Added state=rising for better results
    response = requests.get(url)
    
    if response.status_code == 200:
        articles = response.json()
        with open("txt3.csv", "w", encoding='utf-8') as file:
            for article in articles:
                # Get description with fallbacks
                description = (
                    article.get('description') or 
                    article.get('body_markdown', '').split('\n')[0] or 
                    article.get('title', '')
                )
                
                # Clean and format the description
                description = description.replace('"', '""')
                description = description.replace('\n', ' ').strip()
                
                # Make sure we have some content
                if not description:
                    description = "No description available"
                
                # Get tags
                tags = ', '.join(article.get('tag_list', []))
                
                # Write to CSV
                file.write(f"\"{article['title']}\",\"{description}\",\"{article['url']}\",\"{tags}\"\n")
                
                # Print to console for verification
                print("\n-------------------")
                print(f"Title: {article['title']}")
                print(f"Description: {description}")
                print(f"URL: {article['url']}")
                if tags:
                    print(f"Tags: {tags}")
    else:
        print(f"Failed to fetch articles. Status code: {response.status_code}")

if __name__ == "__main__":
    fetch_dev_to_articles()