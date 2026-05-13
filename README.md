# project_mento

<a target="_blank" href="https://cookiecutter-data-science.drivendata.org/">
    <img src="https://img.shields.io/badge/CCDS-Project%20template-328F97?logo=cookiecutter" />
</a>

ai supervisor for it freshers

MENTO: AI-Powered Career Guidance for IT Freshers

MENTO is a generative AI project aimed at guiding IT freshers through the process of selecting the right courses, learning paths, and career paths. The system leverages machine learning models, Neo4j for knowledge management, and a chatbot interface to provide personalized recommendations.
Project Structure

This project is structured to follow best practices for data science and machine learning workflows. It includes separate folders for data, models, notebooks, and source code.
Features

    AI-powered chatbot for course recommendations
    Neo4j-powered knowledge graph for managing course topics and skills
    Machine learning models for personalized career advice
    Mobile app integration for easy access

Installation

Follow these steps to set up the project on a new machine.
1. Clone the Repository

First, clone the private repository to your local machine:

bash

git clone https://github.com/yourusername/mento.git
cd mento

2. Set Up a Virtual Environment

Before proceeding with the installation, create and activate a Python virtual environment to isolate project dependencies.

bash

# Create a virtual environment
python3 -m venv mento-env

# Activate the virtual environment
# On macOS/Linux
source mento-env/bin/activate

# On Windows
mento-env\Scripts\activate

3. Install Dependencies

Install the required Python packages using the requirements.txt file:

bash

pip install -r requirements.txt


## Project Organization

```
├── LICENSE            <- Open-source license if one is chosen
├── Makefile           <- Makefile with convenience commands like `make data` or `make train`
├── README.md          <- The top-level README for developers using this project.
├── data
│   ├── external       <- Data from third party sources.
│   ├── interim        <- Intermediate data that has been transformed.
│   ├── processed      <- The final, canonical data sets for modeling.
│   └── raw            <- The original, immutable data dump.
│
├── docs               <- A default mkdocs project; see www.mkdocs.org for details
│
├── models             <- Trained and serialized models, model predictions, or model summaries
│
├── notebooks          <- Jupyter notebooks. Naming convention is a number (for ordering),
│                         the creator's initials, and a short `-` delimited description, e.g.
│                         `1.0-jqp-initial-data-exploration`.
│
├── pyproject.toml     <- Project configuration file with package metadata for 
│                         module_mento and configuration for tools like black
│
├── references         <- Data dictionaries, manuals, and all other explanatory materials.
│
├── reports            <- Generated analysis as HTML, PDF, LaTeX, etc.
│   └── figures        <- Generated graphics and figures to be used in reporting
│
├── requirements.txt   <- The requirements file for reproducing the analysis environment, e.g.
│                         generated with `pip freeze > requirements.txt`
│
├── setup.cfg          <- Configuration file for flake8
│
└── module_mento   <- Source code for use in this project.
    │
    ├── __init__.py             <- Makes module_mento a Python module
    │
    ├── config.py               <- Store useful variables and configuration
    │
    ├── dataset.py              <- Scripts to download or generate data
    │
    ├── features.py             <- Code to create features for modeling
    │
    ├── modeling                
    │   ├── __init__.py 
    │   ├── predict.py          <- Code to run model inference with trained models          
    │   └── train.py            <- Code to train models
    │
    └── plots.py                <- Code to create visualizations
```

--------

