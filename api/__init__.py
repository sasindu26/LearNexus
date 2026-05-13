# This file makes the api directory a proper Python package

"""
API package for the Mento application
"""

# You can expose the create_app function here for cleaner imports
from api.main_app import create_app

__all__ = ['create_app']