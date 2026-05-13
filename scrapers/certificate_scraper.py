"""Certificate scraping orchestrator — runs all configured certificate source scrapers."""
import logging
from scrapers.coursera_scraper import CourseraScraper
from scrapers.linkedin_learning_scraper import LinkedInLearningScraper

logger = logging.getLogger(__name__)


class CertificateScraper:
    def run_pipeline(self):
        logger.info("[CertificateScraper] Running all certificate source pipelines...")
        CourseraScraper().run_pipeline()
        LinkedInLearningScraper().run_pipeline()
        logger.info("[CertificateScraper] All certificate source pipelines complete.")
