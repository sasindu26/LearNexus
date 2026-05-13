import requests
from bs4 import BeautifulSoup
import re

url = 'https://www.nsbm.ac.lk/course/bsc-hons-artificial-intelligence-plymouth-university-uk/'
resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
soup = BeautifulSoup(resp.content, 'html.parser')

# Find tables
tables = soup.find_all('table')
print(f"Tables found: {len(tables)}")
for i, t in enumerate(tables):
    cells = [c.get_text(strip=True) for c in t.find_all(['th','td'])[:8]]
    print(f"  Table {i}: {cells}")

# Find year mentions
print("\nYear element mentions:")
for el in soup.find_all(True):
    txt = el.get_text(strip=True)
    if re.match(r'^year\s*\d', txt, re.I) and len(txt) < 30:
        print(f"  <{el.name}> class={el.get('class')} => {txt}")

# Find any "programme contents" or "modules" section
print("\nSearching for module list structure...")
for heading in soup.find_all(['h1','h2','h3','h4']):
    htxt = heading.get_text(strip=True)
    if any(kw in htxt.lower() for kw in ['programme','content','module','year','curriculum']):
        print(f"\nHEADING: {htxt}")
        # Get next sibling content
        nxt = heading.find_next_sibling()
        if nxt:
            print(f"  Next sibling: <{nxt.name}> => {nxt.get_text()[:300]}")
