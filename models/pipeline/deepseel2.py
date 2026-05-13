import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta
import feedparser
import uuid
import re
import umap
import hashlib
from dateutil import parser

# ── Auto-categorization mapping ──────────────────────────────────────────
# Maps frontend category IDs to keywords that trigger that category.
# When an article's title/description/tags contain any keyword, the
# corresponding category tags are added so the frontend filter works.
CATEGORY_KEYWORDS = {
    'ai':            ['ai', 'artificial intelligence', 'machine learning', 'deep learning',
                      'neural network', 'nlp', 'computer vision', 'transformer', 'bert',
                      'classification', 'regression', 'supervised', 'unsupervised'],
    'python':        ['python', 'django', 'fastapi', 'flask', 'pandas', 'numpy',
                      'pytorch', 'tensorflow', 'scikit', 'pip', 'asyncio'],
    'webdev':        ['web dev', 'javascript', 'frontend', 'react', 'nextjs', 'next.js',
                      'css', 'typescript', 'html', 'vue', 'angular', 'svelte', 'tailwind'],
    'devops':        ['devops', 'ci/cd', 'cicd', 'infrastructure', 'gitops', 'sre',
                      'automation', 'terraform', 'ansible', 'jenkins', 'github actions'],
    'cloud':         ['cloud', 'aws', 'azure', 'gcp', 'google cloud', 'serverless',
                      'lambda', 'cloudrun', 'ec2', 's3'],
    'docker':        ['docker', 'kubernetes', 'container', 'k8s', 'helm', 'microservice',
                      'pod', 'orchestration'],
    'cybersecurity': ['cybersecurity', 'security', 'hacking', 'infosec', 'penetration',
                      'vulnerability', 'malware', 'encryption', 'firewall', 'zero trust',
                      'ransomware', 'phishing'],
    'database':      ['database', 'sql', 'neo4j', 'postgres', 'mongodb', 'redis',
                      'mysql', 'nosql', 'graph database', 'data modeling'],
    'datascience':   ['data science', 'data analytics', 'statistics', 'jupyter',
                      'mlops', 'data engineering', 'etl', 'data pipeline',
                      'visualization', 'tableau', 'power bi'],
    'llm':           ['llm', 'gpt', 'langchain', 'openai', 'ollama', 'agents', 'rag',
                      'large language model', 'chatgpt', 'gemini', 'claude', 'copilot',
                      'prompt engineering', 'fine-tuning', 'fine tuning'],
    'networking':    ['networking', 'tcp', 'dns', 'protocol', 'distributed system',
                      'network', 'load balancer', 'proxy', 'vpn', 'firewall'],
    'testing':       ['testing', 'tdd', 'unit test', 'jest', 'qa', 'selenium',
                      'cypress', 'playwright', 'integration test', 'e2e'],
    'softwareengineering': ['software engineering', 'architecture', 'clean code',
                      'refactoring', 'design pattern', 'solid', 'coding', 'algorithm',
                      'data structure', 'system design', 'programming'],
    'mobile':        ['android', 'ios', 'react native', 'flutter', 'swift', 'kotlin',
                      'mobile dev', 'mobile app'],
    'opensource':    ['open source', 'opensource', 'github', 'contribution', 'oss',
                      'foss', 'git'],
    'blockchain':    ['blockchain', 'web3', 'crypto', 'defi', 'smart contract',
                      'ethereum', 'solidity', 'nft'],
    'career':        ['career', 'jobs', 'hiring', 'interview', 'resume', 'salary',
                      'remote work', 'freelance', 'linkedin'],
}


def categorize_article(title, existing_tags, description=''):
    """
    Enrich article tags with category-specific keywords by scanning the
    article's title, existing tags, and description for keyword matches.
    Returns a deduplicated list of tags.
    """
    search_text = f"{title} {description} {' '.join(existing_tags)}".lower()

    enriched = set(t.lower().strip() for t in existing_tags if t)

    for cat_id, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in search_text for kw in keywords):
            # Add the category ID as a tag (matches frontend filter)
            enriched.add(cat_id)
            # Also add the first 1-2 specific matching keywords for display
            for kw in keywords[:3]:
                if kw in search_text:
                    enriched.add(kw.replace(' ', ''))
                    break

    return list(enriched)


def preprocess_text(text):
    """
    Preprocess text by removing HTML tags, special characters, and normalizing.
    
    Args:
        text (str): Raw text to preprocess
        
    Returns:
        str: Cleaned and preprocessed text
    """
    if not text:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    
    # Remove special characters but keep spaces and basic punctuation
    text = re.sub(r'[^a-zA-Z0-9\s.,!?-]', '', text)
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove extra whitespace and normalize
    text = ' '.join(text.split())
    
    # Remove very short words (less than 2 characters)
    words = text.split()
    words = [word for word in words if len(word) >= 2]
    
    return ' '.join(words)

def fetch_devto_articles(tag=None, max_articles=50):
    """
    Fetches articles from Dev.to API with given tag.
    
    Args:
        tag (str): Tag to filter articles.
        max_articles (int): Maximum number of articles to fetch.
    
    Returns:
        list: List of article data with source tag.
    """
    base_url = "https://dev.to/api/articles"
    params = {"per_page": max_articles}
    
    if tag:
        params["tag"] = tag
    
    try:
        response = requests.get(base_url, params=params, timeout=10)
        if response.status_code != 200:
            print(f"Error fetching Dev.to articles: {response.status_code}")
            return []
        
        articles_data = response.json()
        articles = []
        
        for article in articles_data:
            # Extract cover image — skip articles without one
            cover = article.get("cover_image") or article.get("social_image") or ""
            if not cover or not cover.strip():
                continue

            article_data = {
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "tags": article.get("tag_list", []),
                "published_at": article.get("published_at", ""),
                "description": article.get("description", ""),
                "cover_image": cover.strip(),
                "source": "dev.to"
            }
            
            if article_data["url"]:
                full_description = scrape_full_description(article_data["url"])
                if full_description:
                    article_data["full_description"] = full_description
            
            articles.append(article_data)
        
        return articles
    
    except Exception as e:
        print(f"Error fetching Dev.to articles: {e}")
        return []

def fetch_dailydev_articles(tag=None, max_articles=50):
    """
    Fetches articles from Medium via their public RSS feed (tag-based).
    Originally this used daily.dev, but their API and RSS are both dead.
    Medium serves as a high-quality replacement with cover images.
    
    Args:
        tag (str): Tag to filter articles (e.g. 'technology', 'python').
        max_articles (int): Maximum number of articles to fetch.
    
    Returns:
        list: List of article data with source tag.
    """
    _headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    }

    feed_tag = tag or "technology"
    rss_url = f"https://medium.com/feed/tag/{feed_tag}"
    
    try:
        feed = feedparser.parse(rss_url)
        articles = []
        
        for entry in feed.entries[:max_articles]:
            title = entry.get("title", "")
            url = entry.get("link", "").split("?")[0]  # Remove tracking params
            published = entry.get("published", "")

            # Medium RSS includes partial HTML content in content[0]
            content_html = ""
            if entry.get("content"):
                content_html = entry["content"][0].get("value", "")
            elif entry.get("summary"):
                content_html = entry["summary"]

            # Extract first image from content as cover image
            cover = ""
            if content_html:
                img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content_html)
                if img_match:
                    cover = img_match.group(1)

            # Also try og:image from the actual page if no inline image
            if not cover and url:
                try:
                    resp = requests.get(url, timeout=10, headers=_headers,
                                        allow_redirects=True)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        og = soup.find("meta", property="og:image")
                        if og and og.get("content"):
                            cover = og["content"]
                except Exception:
                    pass

            # Clean description from HTML
            description = re.sub(r'<[^>]+>', '', content_html[:500]).strip()
            if len(description) > 200:
                description = description[:200] + "..."

            # Skip articles without a cover image
            if not cover or not cover.strip():
                continue

            # Scrape full article content from the actual page
            full_description = ""
            if url:
                full_description = scrape_full_description(url)
            # Fall back to RSS content if scraping failed
            if not full_description or len(full_description) < 200:
                full_description = content_html or f"<p>{description}</p>"

            article_data = {
                "title": title,
                "url": url,
                "tags": [feed_tag],
                "published_at": published,
                "description": description,
                "full_description": full_description,
                "cover_image": cover.strip(),
                "source": "daily.dev"  # Keep source name for backward compatibility
            }
            articles.append(article_data)
        
        return articles
    
    except Exception as e:
        print(f"Error fetching Medium/daily.dev articles: {e}")
        return []

def _resolve_google_news_url(gnews_url, headers):
    """Resolve a Google News redirect URL to the actual article URL.

    Uses the googlenewsdecoder library which queries Google's servers
    to resolve the opaque article ID to the real URL.
    Falls back to direct HTTP fetch if the decoder is unavailable.
    """
    # Strategy 1: Use googlenewsdecoder (reliable since Google changed encoding in 2024)
    try:
        from googlenewsdecoder import gnewsdecoder
        result = gnewsdecoder(gnews_url)
        if result.get("status") and result.get("decoded_url"):
            real_url = result["decoded_url"]
            # Fetch the actual page to get HTML for og:image extraction
            try:
                resp = requests.get(real_url, timeout=12, headers=headers,
                                    allow_redirects=True)
                if resp.status_code == 200:
                    return resp.url, resp.text
            except Exception:
                pass
            return real_url, ""
    except ImportError:
        print("[WARN] googlenewsdecoder not installed. Run: pip install googlenewsdecoder")
    except Exception as e:
        print(f"[WARN] gnewsdecoder failed for {gnews_url[:80]}: {e}")

    # Strategy 2: Fall back to HTTP redirects
    try:
        resp = requests.get(gnews_url, timeout=12, headers=headers,
                            allow_redirects=True)
        if resp.status_code == 200 and 'news.google.com' not in resp.url:
            return resp.url, resp.text
        return gnews_url, resp.text if resp.status_code == 200 else ""
    except Exception:
        return gnews_url, ""


def _is_placeholder_image(url):
    """Check if an image URL is a known generic/placeholder image."""
    if not url:
        return True
    placeholders = [
        "news.google.com",
        "lh3.googleusercontent.com",   # Google News RSS thumbnail — always the same placeholder
        "googleusercontent.com/J6_coFbogxhRI9iM864",  # exact Google News placeholder
        "google.com/images/branding",
        "google.com/logos",
        "gstatic.com/images/branding",
        "gstatic.com/generate_204",
        "schema.org",
        "1x1",
        "pixel",
        "spacer",
        "blank.gif",
        "transparent.png",
    ]
    url_lower = url.lower()
    return any(p in url_lower for p in placeholders)


def fetch_google_news_tech(max_articles=50):
    """
    Fetches tech news from Google News RSS feed.
    
    Args:
        max_articles (int): Maximum number of articles to fetch.
    
    Returns:
        list: List of article data with source tag.
    """
    rss_url = "https://news.google.com/rss/search?q=technology&hl=en-US&gl=US&ceid=US:en"
    _headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    try:
        feed = feedparser.parse(rss_url)
        articles = []
        
        for entry in feed.entries[:max_articles]:
            # Try to extract image from RSS media or by scraping the page
            cover = ""
            # Check for media:content or media:thumbnail in RSS
            if hasattr(entry, 'media_content') and entry.media_content:
                cover = entry.media_content[0].get('url', '') if entry.media_content else ''
            elif hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
                cover = entry.media_thumbnail[0].get('url', '') if entry.media_thumbnail else ''

            # Filter out Google placeholder images from RSS
            if _is_placeholder_image(cover):
                cover = ""

            # Google News RSS description is usually just HTML with title + source,
            # not real article text.  Clean it to plain text and try to get real
            # description from the page itself.
            rss_desc_raw = entry.get("description", "")
            rss_desc_clean = re.sub(r'<[^>]+>', '', rss_desc_raw).strip()

            page_description = ""
            # Resolve Google News redirect to actual article URL
            real_url = entry.get("link", "")
            if real_url:
                try:
                    resolved_url, page_html = _resolve_google_news_url(real_url, _headers)
                    if resolved_url and 'news.google.com' not in resolved_url:
                        real_url = resolved_url

                    if page_html:
                        soup = BeautifulSoup(page_html, "html.parser")
                        # Get og:image from the ACTUAL article page
                        if not cover or _is_placeholder_image(cover):
                            og = soup.find("meta", property="og:image")
                            if og and og.get("content") and not _is_placeholder_image(og["content"]):
                                cover = og["content"]
                        # Also try twitter:image (many sites set this)
                        if not cover or _is_placeholder_image(cover):
                            tw = soup.find("meta", attrs={"name": "twitter:image"})
                            if not tw:
                                tw = soup.find("meta", property="twitter:image")
                            if tw and tw.get("content") and not _is_placeholder_image(tw["content"]):
                                cover = tw["content"]
                        # Get og:description as a better short description
                        og_desc = soup.find("meta", property="og:description")
                        if og_desc and og_desc.get("content") and len(og_desc["content"]) > 30:
                            page_description = og_desc["content"]
                        elif not page_description:
                            meta_desc = soup.find("meta", attrs={"name": "description"})
                            if meta_desc and meta_desc.get("content") and len(meta_desc["content"]) > 30:
                                page_description = meta_desc["content"]
                except Exception:
                    pass

            # Skip articles without a valid cover image
            if not cover or not cover.strip() or _is_placeholder_image(cover):
                continue

            # Use the best available description
            best_description = page_description or rss_desc_clean

            article_data = {
                "title": entry.get("title", ""),
                "url": real_url,  # Use resolved URL, not Google News redirect
                "tags": ["technology"],  # Default tag since RSS doesn't provide tags
                "published_at": entry.get("published", ""),
                "description": best_description,
                "cover_image": cover.strip(),
                "source": "google_news"
            }
            
            if article_data["url"]:
                full_description = scrape_full_description(article_data["url"])
                if full_description:
                    article_data["full_description"] = full_description
                else:
                    # Use the page description as fallback, wrapped in HTML
                    article_data["full_description"] = f"<p>{best_description}</p>" if best_description else ""
            
            articles.append(article_data)
        
        return articles
    
    except Exception as e:
        print(f"Error fetching Google News articles: {e}")
        return []


def scrape_full_description(article_url):
    """
    Returns full HTML content for an article URL.
    For dev.to URLs, uses the official API (body_html field) — fast and reliable.
    Falls back to BeautifulSoup scraping for other sources.
    Handles Google News redirect URLs and uses a realistic User-Agent.
    """
    try:
        # Use a realistic browser User-Agent so news sites don't block us
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        # Dev.to: use the public API — much more reliable than scraping JS-rendered pages
        if 'dev.to/' in article_url:
            try:
                path = article_url.split('dev.to/')[-1].strip('/').split('?')[0]
                parts = path.split('/')
                if len(parts) >= 2:
                    api_url = f"https://dev.to/api/articles/{parts[0]}/{parts[1]}"
                    api_resp = requests.get(api_url, timeout=10, headers=headers)
                    if api_resp.status_code == 200:
                        data = api_resp.json()
                        body_html = data.get('body_html', '')
                        if body_html and len(body_html) > 200:
                            return body_html
            except Exception:
                pass  # fall through to scraping

        # Follow redirects (important for Google News URLs which 302 to actual sites)
        response = requests.get(article_url, timeout=15, headers=headers,
                                allow_redirects=True)
        if response.status_code != 200:
            return ""

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove non-content elements
        for tag in soup.find_all(["nav", "footer", "script", "style", "aside",
                                   "header", "noscript", "iframe", "form"]):
            tag.decompose()

        # Extended content selectors covering major news sites
        content_selectors = [
            # Medium
            "section.pw-post-body-paragraph",
            "div.meteredContent",
            "article section",
            # Dev.to / blogging
            "article.article",
            "div.article__body",
            # Generic
            "main article",
            "article",
            # News sites
            "div.article-content",
            "div.article-body",
            "div.article__content",
            "div.story-body",
            "div.story-content",
            "div.caas-body",              # Yahoo News / Yahoo Finance
            "div.caas-content-wrapper",   # Yahoo
            "div.post-content",
            "div.entry-content",
            "div.content-body",
            "div.article-text",
            "div.article_body",
            "section.article-body",
            "div[data-testid='article-body']",
            "div.StandardArticleBody_body",
            "div.paywall",                # some paywalled sites still render HTML
            "main",
            "div.content",
            "div#article-body",
            "div#story-body",
        ]

        for selector in content_selectors:
            content = soup.select_one(selector)
            if content and len(content.get_text(strip=True)) > 200:
                return str(content)

        # Fallback: gather all <p> tags with meaningful text
        paragraphs = soup.find_all("p")
        if paragraphs:
            html = "".join(str(p) for p in paragraphs if len(p.get_text(strip=True)) > 20)
            if len(html) > 200:
                return f"<div>{html}</div>"

        # Last resort: check og:description meta tag for at least a summary
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content") and len(og_desc["content"]) > 50:
            return f"<p>{og_desc['content']}</p>"

        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content") and len(meta_desc["content"]) > 50:
            return f"<p>{meta_desc['content']}</p>"

        return ""

    except Exception as e:
        print(f"Error scraping {article_url}: {e}")
        return ""

def filter_articles_by_time(articles, last_run_time=None, hours_lookback=24):
    """
    Filter articles to only include those published after the last run time
    
    Args:
        articles (list): List of articles to filter
        last_run_time (datetime): Last time the pipeline ran
        hours_lookback (int): Hours to look back if no last_run_time
    
    Returns:
        list: Filtered articles
    """
    if not articles:
        return []
    
    # If no last run time, look back specified hours
    if not last_run_time:
        cutoff_time = datetime.now() - timedelta(hours=hours_lookback)
    else:
        cutoff_time = last_run_time
    
    filtered_articles = []
    
    for article in articles:
        published_at = article.get('published_at', '')
        
        if not published_at:
            # If no publish date, include it to be safe
            filtered_articles.append(article)
            continue
        
        try:
            # Parse the published date
            if isinstance(published_at, str):
                # Handle different date formats
                if 'T' in published_at:
                    # ISO format: 2024-01-15T10:30:00Z
                    article_date = parser.parse(published_at)
                else:
                    # Try parsing other formats
                    article_date = parser.parse(published_at)
            else:
                article_date = published_at
            
            # Make timezone-naive for comparison
            if article_date.tzinfo is not None:
                article_date = article_date.replace(tzinfo=None)
            if cutoff_time.tzinfo is not None:
                cutoff_time = cutoff_time.replace(tzinfo=None)
            
            # Only include articles published after cutoff time
            if article_date > cutoff_time:
                filtered_articles.append(article)
                
        except Exception as e:
            print(f"Error parsing date '{published_at}': {e}")
            # Include article if we can't parse the date
            filtered_articles.append(article)
    
    print(f"Time filter: {len(articles)} total -> {len(filtered_articles)} recent articles")
    return filtered_articles

def get_last_pipeline_run_time(graph):
    """Get the last time the pipeline was run from the database"""
    try:
        result = graph.run("""
            MATCH (a:Article) 
            RETURN max(a.created_date) as last_created
        """).data()
        
        if result and result[0]['last_created']:
            # Convert Neo4j datetime to Python datetime
            last_created = result[0]['last_created']
            if hasattr(last_created, 'to_native'):
                return last_created.to_native()
            return last_created
            
    except Exception as e:
        print(f"Error getting last run time: {e}")
    
    return None

def generate_content_hash(content):
    """Generate hash for article content to detect duplicates"""
    if not content:
        return ""
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def check_existing_articles(articles, graph):
    """Check which articles already exist in the database"""
    if not articles:
        return [], []
    
    # Extract URLs and titles from fetched articles
    article_data = []
    for article in articles:
        content = f"{article.get('title', '')} {article.get('description', '')} {article.get('full_description', '')}"
        content_hash = generate_content_hash(content)
        article_data.append({
            'url': article.get('url', ''),
            'title': article.get('title', ''),
            'content_hash': content_hash
        })
    
    # Check which articles already exist (by URL, title, or content hash)
    try:
        existing_check = graph.run("""
            UNWIND $articles_data AS article_data
            MATCH (a:Article)
            WHERE a.url = article_data.url 
               OR a.title = article_data.title 
               OR a.content_hash = article_data.content_hash
            RETURN article_data.url as url, article_data.title as title, article_data.content_hash as content_hash
        """, articles_data=article_data).data()
    except Exception as e:
        print(f"Error checking existing articles: {e}")
        existing_check = []
    
    # Create set of existing identifiers
    existing_urls = {item['url'] for item in existing_check if item['url']}
    existing_titles = {item['title'] for item in existing_check if item['title']}
    existing_hashes = {item['content_hash'] for item in existing_check if item['content_hash']}
    
    # Filter out duplicates
    new_articles = []
    duplicate_articles = []
    
    for i, article in enumerate(articles):
        url = article.get('url', '')
        title = article.get('title', '')
        content_hash = article_data[i]['content_hash']
        
        if url in existing_urls or title in existing_titles or content_hash in existing_hashes:
            duplicate_articles.append(article)
        else:
            article['content_hash'] = content_hash  # Add hash to article
            new_articles.append(article)
    
    return new_articles, duplicate_articles

def process_articles_to_neo4j(articles, graph, embedding_model):
    """
    Process articles and store directly to Neo4j with enhanced duplicate prevention
    
    Args:
        articles (list): List of article data
        graph: Neo4j graph connection
        embedding_model: Model to generate embeddings
        
    Returns:
        int: Number of articles processed
    """
    if not articles:
        return 0
        
    # Create constraint to prevent URL duplicates
    try:
        graph.run("CREATE CONSTRAINT article_url_unique IF NOT EXISTS FOR (a:Article) REQUIRE a.url IS UNIQUE")
    except Exception as e:
        print(f"Constraint already exists or error creating it: {e}")
    
    processed_count = 0
    
    for article in articles:
        try:
            title = article.get("title", "")
            url = article.get("url", "")
            tags = article.get("tags", [])
            description = article.get("preprocessed_description", article.get("description", ""))
            full_description = article.get("full_description", "")
            source = article.get("source", "unknown")
            content_hash = article.get("content_hash", "")
            cover_image = article.get("cover_image", "")
            published_at = article.get("published_at", "")
            
            # Skip articles without necessary info
            if not title or not url or not description:
                print(f"Skipping article due to missing info: {title}")
                continue
            
            # Skip articles without a cover image
            if not cover_image or not cover_image.strip():
                print(f"Skipping article without cover image: {title}")
                continue
            
            # Double-check if article exists (race condition protection)
            existing = graph.run("""
                MATCH (a:Article) 
                WHERE a.url = $url OR a.title = $title OR a.content_hash = $content_hash
                RETURN count(a) as count
            """, url=url, title=title, content_hash=content_hash).data()[0]['count']
            
            if existing > 0:
                print(f"Article already exists, skipping: {title}")
                continue

            # ── Auto-categorize: enrich tags with category keywords ──
            tags = categorize_article(title, tags, description)

            # ── Create a clean short_description (no HTML) for card previews ──
            raw_desc = full_description or description
            short_description = re.sub(r'<[^>]+>', ' ', raw_desc)
            short_description = ' '.join(short_description.split()).strip()[:300]

            # Generate embedding for full description
            content = f"{title} {description} {full_description}"
            embedding = embedding_model.encode(content).tolist()
            
            # Create Article node with enhanced data
            graph.run("""
                MERGE (a:Article {url: $url})
                SET a.title = $title,
                    a.description = $description,
                    a.full_description = $full_description,
                    a.short_description = $short_description,
                    a.tags = $tags,
                    a.embedding = $embedding,
                    a.source = $source,
                    a.content_hash = $content_hash,
                    a.cover_image = $cover_image,
                    a.published_at = $published_at,
                    a.created_date = datetime(),
                    a.processed_date = $processed_date
            """, 
                url=url, 
                title=title, 
                description=description,
                full_description=full_description,
                short_description=short_description,
                tags=tags,
                embedding=embedding, 
                source=source,
                content_hash=content_hash,
                cover_image=cover_image,
                published_at=published_at,
                processed_date=datetime.now().isoformat()
            )
            
            # Create Tag nodes and relationships
            for tag in tags:
                if tag:  # Skip empty tags
                    graph.run("""
                        MERGE (t:Tag {name: $tag})
                        WITH t
                        MATCH (a:Article {url: $url})
                        MERGE (a)-[:HAS_TAG]->(t)
                    """, tag=str(tag).lower().strip(), url=url)
            
            # Create Source node and relationship
            graph.run("""
                MERGE (s:Source {name: $source})
                WITH s
                MATCH (a:Article {url: $url})
                MERGE (a)-[:FROM_SOURCE]->(s)
            """, source=source, url=url)
            
            processed_count += 1
            print(f"Successfully processed article: {title}")
            
        except Exception as e:
            print(f"Error processing article {article.get('url', 'unknown')}: {e}")
            continue
            
    return processed_count

def fetch_all_tech_news(tags=None, max_articles_per_source=50, graph=None, use_time_filter=True):
    """
    Fetches tech news from multiple sources with comprehensive duplicate prevention.
    
    Args:
        tags (list): List of tags to filter articles.
        max_articles_per_source (int): Max articles per source.
        graph: Neo4j graph connection for time-based filtering
        use_time_filter (bool): Whether to filter by time
    
    Returns:
        list: Combined list of unique, recent articles from all sources.
    """
    all_articles = []
    
    # Get last pipeline run time for filtering
    last_run_time = None
    if graph and use_time_filter:
        last_run_time = get_last_pipeline_run_time(graph)
        print(f"Last pipeline run: {last_run_time}")
    
    # Fetch from Dev.to
    print("Fetching from Dev.to...")
    for tag in tags or [None]:
        dev_articles = fetch_devto_articles(tag, max_articles_per_source)
        all_articles.extend(dev_articles)
    
    # Fetch from daily.dev  
    print("Fetching from daily.dev...")
    for tag in tags or [None]:
        daily_articles = fetch_dailydev_articles(tag, max_articles_per_source)
        all_articles.extend(daily_articles)
    
    # Fetch from Google News
    print("Fetching from Google News...")
    google_articles = fetch_google_news_tech(max_articles_per_source)
    all_articles.extend(google_articles)
    
    print(f"Total articles fetched from all sources: {len(all_articles)}")
    
    # Apply time-based filtering first
    if use_time_filter:
        all_articles = filter_articles_by_time(all_articles, last_run_time)
    
    # Preprocess all articles and add content hashes
    for article in all_articles:
        content = f"{article.get('title', '')} {article.get('description', '')} {article.get('full_description', '')}"
        article['preprocessed_description'] = preprocess_text(content)
        article['content_hash'] = generate_content_hash(content)
    
    # Remove duplicates based on URL and content similarity within this batch
    unique_articles = []
    seen_urls = set()
    seen_hashes = set()
    
    for article in all_articles:
        url = article.get('url', '')
        content_hash = article.get('content_hash', '')
        
        # Skip if we've already seen this URL or content
        if url and url in seen_urls:
            continue
        if content_hash and content_hash in seen_hashes:
            continue
        
        # Add to unique list
        unique_articles.append(article)
        if url:
            seen_urls.add(url)
        if content_hash:
            seen_hashes.add(content_hash)
    
    print(f"After deduplication: {len(unique_articles)} unique articles")
    return unique_articles

# Example usage
if __name__ == "__main__":
    from py2neo import Graph
    from sentence_transformers import SentenceTransformer
    
    # Initialize Neo4j connection and embedding model
    graph = Graph("bolt://localhost:7691", auth=("neo4j", "password"))
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    
    # Fetch articles with specific tags
    tags = ["mechineLearning" , "deepLearning" , "networking" , "security" , "IT"]
    articles = fetch_all_tech_news(tags, max_articles_per_source=3)
    
    # Process articles to Neo4j
    processed = process_articles_to_neo4j(articles, graph, embedding_model)
    print(f"Processed {processed} articles to Neo4j")