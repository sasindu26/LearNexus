"""Abstract base class for all scrapers."""
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class BaseScraper(ABC):

    @abstractmethod
    def scrape(self) -> list:
        """Fetch raw items from the source. Return list of raw dicts."""

    @abstractmethod
    def normalize(self, raw: dict) -> dict:
        """Transform a raw item into the canonical schema dict."""

    @abstractmethod
    def store(self, items: list):
        """Persist normalized items to Neo4j."""

    def run_pipeline(self):
        """Template method: scrape → normalize → store."""
        logger.info(f"[{self.__class__.__name__}] Starting pipeline...")
        try:
            raw_items = self.scrape()
            logger.info(f"[{self.__class__.__name__}] Scraped {len(raw_items)} raw items")
            normalized = [self.normalize(r) for r in raw_items if r]
            normalized = [n for n in normalized if n]
            logger.info(f"[{self.__class__.__name__}] Normalized {len(normalized)} items")
            self.store(normalized)
            logger.info(f"[{self.__class__.__name__}] Pipeline complete.")
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Pipeline failed: {e}")
