#################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_NAME = mento_repo
PYTHON_VERSION = 3.11
PYTHON_INTERPRETER = python3
VENV_NAME = venv

#################################################################################
# COMMANDS                                                                      #
#################################################################################

.PHONY: all clean install test lint requirements dev-requirements venv setup

all: venv requirements

venv:
	$(PYTHON_INTERPRETER) -m venv $(VENV_NAME)
	. $(VENV_NAME)/bin/activate && \
	$(PYTHON_INTERPRETER) -m pip install --upgrade pip setuptools wheel

requirements: venv
	. $(VENV_NAME)/bin/activate && \
	$(PYTHON_INTERPRETER) -m pip install -e . && \
	$(PYTHON_INTERPRETER) -m pip install -r requirements.txt

dev-requirements: requirements
	. $(VENV_NAME)/bin/activate && \
	$(PYTHON_INTERPRETER) -m pip install -r requirements-dev.txt

setup:
	$(PYTHON_INTERPRETER) setup.py develop

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.py[co]" -delete
	find . -type f -name "*.so" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name ".tox" -exec rm -rf {} +
	find . -type d -name ".eggs" -exec rm -rf {} +
	find . -type f -name "*.log" -delete
	rm -rf build/
	rm -rf dist/
	rm -rf .eggs/
	rm -rf $(VENV_NAME)

lint:
	. $(VENV_NAME)/bin/activate && \
	flake8 . && \
	black . --check && \
	isort . --check-only

test:
	. $(VENV_NAME)/bin/activate && \
	pytest tests/ -v --cov=mento_repo

format:
	. $(VENV_NAME)/bin/activate && \
	black . && \
	isort .

help:
	@echo "make                    - Install all dependencies and set up project"
	@echo "make venv              - Create virtual environment"
	@echo "make requirements      - Install production dependencies"
	@echo "make dev-requirements  - Install development dependencies"
	@echo "make setup            - Install package in development mode"
	@echo "make clean            - Remove all build, test, and Python artifacts"
	@echo "make lint             - Check code style"
	@echo "make test             - Run tests"
	@echo "make format           - Format code"
