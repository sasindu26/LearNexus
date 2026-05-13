import requests
from bs4 import BeautifulSoup
import re

url = 'https://www.nsbm.ac.lk/course/bsc-hons-artificial-intelligence-plymouth-university-uk/'
resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
soup = BeautifulSoup(resp.content, 'html.parser')

# Find all Year h2 headings (Elementor style)
year_headings = soup.find_all('h2', class_='elementor-heading-title')
print(f"Year headings found: {[h.get_text(strip=True) for h in year_headings]}")

# For each year heading, find the icon-list items that follow
for h2 in year_headings:
    ht = h2.get_text(strip=True)
    if not re.match(r'year\s*\d', ht, re.I):
        continue
    print(f"\n=== {ht} ===")
    
    # Walk up to find the column/section container, then find next column's list
    # Elementor structure: section > column > widget(heading) | column > widget(icon-list)
    parent_col = h2.find_parent('div', class_=re.compile('elementor-column'))
    if parent_col:
        parent_section = parent_col.find_parent('section') or parent_col.find_parent('div', class_=re.compile('elementor-section'))
        if parent_section:
            # Find all icon-list items in this section
            items = parent_section.find_all('li', class_=re.compile('elementor-icon-list-item'))
            if items:
                for li in items:
                    print(f"  MODULE: {li.get_text(strip=True)}")
            else:
                # Try text-editor widgets
                widgets = parent_section.find_all('div', class_=re.compile('elementor-widget-text-editor'))
                for w in widgets:
                    for li in w.find_all('li'):
                        print(f"  MODULE: {li.get_text(strip=True)}")
                    for p in w.find_all('p'):
                        print(f"  MODULE: {p.get_text(strip=True)}")
