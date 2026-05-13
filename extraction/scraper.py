import requests
from bs4 import BeautifulSoup
import pandas as pd

def extract_modules_by_year(url):
    # Send a request to the university site
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to retrieve page: {url}")
        return None
    
    # Parse the HTML content
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Define the data-id for each year
    year_ids = {
        "1st Year": "1a46983",
        "2nd Year": "08e7c80",
        "3rd Year": "64138a9",
        "4th Year": "f6b6454"
    }
    
    all_years_modules = {}

    # Loop through each year's div and extract module names
    for year, year_id in year_ids.items():
        # Find the div with the specific data-id for the year
        year_div = soup.find('div', {'data-id': year_id})
        
        if not year_div:
            print(f"Year '{year}' with id '{year_id}' not found.")
            continue
        
        # Find all module names inside this year's div
        modules = year_div.find_all('span', {'data-text': True})
        module_names = [module['data-text'] for module in modules]
        
        all_years_modules[year] = module_names
    
    return all_years_modules

def store_modules_for_courses(course_urls, output_filename):
    # Define the DataFrame structure to store all courses
    df = pd.DataFrame(columns=["Level 1", "Level 2", "Level 3", "Level 4", "Course"])
    
    for course_name, url in course_urls.items():
        # Extract modules by year for each course
        all_years_modules = extract_modules_by_year(url)
        if all_years_modules is None:
            continue
        
        # Find the maximum number of modules in any year
        max_modules = max(len(modules) for modules in all_years_modules.values())
        
        # Create a dictionary to store the modules for this course
        data = {
            "Level 1": [],
            "Level 2": [],
            "Level 3": [],
            "Level 4": [],
            "Course": []
        }
        
        # Loop through the maximum number of module entries and append modules
        for i in range(max_modules):
            data["Level 1"].append(all_years_modules.get("1st Year", [None])[i] if i < len(all_years_modules.get("1st Year", [])) else None)
            data["Level 2"].append(all_years_modules.get("2nd Year", [None])[i] if i < len(all_years_modules.get("2nd Year", [])) else None)
            data["Level 3"].append(all_years_modules.get("3rd Year", [None])[i] if i < len(all_years_modules.get("3rd Year", [])) else None)
            data["Level 4"].append(all_years_modules.get("4th Year", [None])[i] if i < len(all_years_modules.get("4th Year", [])) else None)
            data["Course"].append(course_name)
        
        # Append the course's data to the DataFrame
        df = pd.concat([df, pd.DataFrame(data)], ignore_index=True)
    
    # Save DataFrame to CSV
    df.to_csv(output_filename, index=False)
    print(f"Data saved to {output_filename}")

if __name__ == '__main__':
    # Define the course URLs
    course_urls = {
        "Data Science": "https://www.nsbm.ac.lk/course/bsc-honors-in-data-science/",
        "Computer Science": "https://www.nsbm.ac.lk/course/bachelor-of-science-honours-in-computer-science-bsc-honours-in-computer-science-ugc/",
        "Software Engineering": "https://www.nsbm.ac.lk/course/bsc-honours-in-software-engineering/",
        "Management Information Systems": "https://www.nsbm.ac.lk/course/bsc-in-management-information-systems-special-ugc/",
        "Computer Networks": "https://www.nsbm.ac.lk/course/bsc-honours-in-computer-networks-ugc/"
    }
    
    # Store modules from multiple courses in a CSV file
    store_modules_for_courses(course_urls, 'multiple_courses_modules2.csv')
