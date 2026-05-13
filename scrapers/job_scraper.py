"""Job scraping orchestrator — runs all configured job source scrapers."""
import logging
from scrapers.remoteok_scraper import RemoteOKScraper
from scrapers.adzuna_scraper import AdzunaScraper

logger = logging.getLogger(__name__)


class JobScraper:
    def run_pipeline(self):
        logger.info("[JobScraper] Running all job source pipelines...")
        RemoteOKScraper().run_pipeline()
        AdzunaScraper().run_pipeline()
        logger.info("[JobScraper] All job source pipelines complete.")
