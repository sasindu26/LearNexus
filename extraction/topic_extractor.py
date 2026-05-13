import pandas as pd
import os
from googlesearch import search
import csv
from dotenv import load_dotenv

# Function to perform Google search and extract URLs with priority for certain websites
def google_search(query, num_results=10):
    # Perform Google search and extract URLs
    search_results = search(query, num=num_results, stop=num_results, pause=4.0)
    
    # List of priority websites
    priority_sites = ['geeksforgeeks.org', 'medium.com', 'w3schools.com', 'datacamp.com']
    priority_urls = []
    other_urls = []

    # Categorize URLs based on priority
    for url in search_results:
        if any(site in url for site in priority_sites):
            priority_urls.append(url)
        else:
            other_urls.append(url)

    # Combine priority URLs with other URLs
    all_urls = priority_urls + other_urls
    
    return all_urls

# Function to save search results to a new CSV file in the specified output directory
def save_topic_results_to_csv(module_name, topic_name, urls, output_file):
    # Save search results for each topic to the output CSV
    with open(output_file, mode='a', newline='') as file:
        writer = csv.writer(file)
        # Write the module name, topic name, and URLs
        for url in urls:
            writer.writerow([module_name, topic_name, url])

# Function to process the topics in the CSV and perform Google searches
def process_topics_csv(input_file, output_directory='output', num_results=10):
    # Read the input CSV
    topics_df = pd.read_csv(input_file)

    # Ensure the output directory exists
    os.makedirs(output_directory, exist_ok=True)

    # Generate the output file name by appending '_urls' to the input file name and saving it to the output directory
    output_file_name = os.path.basename(input_file).replace('.csv', '_urls.csv')
    output_file_path = os.path.join(output_directory, output_file_name)

    # Iterate through each row in the CSV (Module, Topic)
    for index, row in topics_df.iterrows():
        module_name = row['Module'].strip()
        topic_name = row['Topic'].strip()
        print(f"Searching for topic: {topic_name} (Module: {module_name})")
        
        # Perform Google search for the topic
        urls = google_search(topic_name, num_results)

        # Save the search results into the output CSV
        save_topic_results_to_csv(module_name, topic_name, urls, output_file_path)

    print(f"Search results saved to {output_file_path}")

# Load environment variables from .env file
load_dotenv()

# Example usage
input_file = 'mento_repo/extraction/data_sets/module_subtopics/DS_3.csv'  # Replace this with the path to your CSV file
output_directory = 'mento_repo/extraction/data_sets/module_subtopics_urls/'  # Replace this with the desired output directory

# List of input files to process
input_files = [
    'mento_repo/extraction/data_sets/module_subtopics/MIS_3.csv',
    'mento_repo/extraction/data_sets/module_subtopics/MIS_4.csv',
    'mento_repo/extraction/data_sets/module_subtopics/SE_3.csv',
    'mento_repo/extraction/data_sets/module_subtopics/SE_4.csv',
]

# Loop through each input file and process it
for input_file in input_files:
    process_topics_csv(input_file, output_directory, num_results=10)


