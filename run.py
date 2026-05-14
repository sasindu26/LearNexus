#!/usr/bin/env python
"""
Main entry point for the LearNexus AI application.
"""
import os
import sys
import logging
import threading
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('learnexus_app')

project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.append(project_root)


def _run_scraping_pipeline():
    """Run the technology, job, and certificate scraping pipelines."""
    try:
        pipeline_dir = os.path.join(project_root, 'models', 'pipeline')
        if pipeline_dir not in sys.path:
            sys.path.insert(0, pipeline_dir)
        from technology_pipeline import TechnologyPipeline
        logger.info("[Scheduler] Starting daily article scraping pipeline...")
        pipeline = TechnologyPipeline()
        pipeline.process_new_articles()
        logger.info("[Scheduler] Article scraping complete.")
    except Exception as e:
        logger.error(f"[Scheduler] Article scraping failed: {e}")

    try:
        from scrapers.job_scraper import JobScraper
        logger.info("[Scheduler] Starting job scraping pipeline...")
        JobScraper().run_pipeline()
        logger.info("[Scheduler] Job scraping complete.")
    except Exception as e:
        logger.error(f"[Scheduler] Job scraping failed: {e}")

    try:
        from scrapers.certificate_scraper import CertificateScraper
        logger.info("[Scheduler] Starting certificate scraping pipeline...")
        CertificateScraper().run_pipeline()
        logger.info("[Scheduler] Certificate scraping complete.")
    except Exception as e:
        logger.error(f"[Scheduler] Certificate scraping failed: {e}")


def _start_daily_scheduler():
    """Background thread: run scraping once immediately, then every 24 hours."""
    # Wait 30 s after startup before first run so the app is fully initialized
    time.sleep(30)
    _run_scraping_pipeline()
    while True:
        time.sleep(24 * 60 * 60)   # 24 hours
        _run_scraping_pipeline()


from api.main_app import create_app

if __name__ == "__main__":
    logger.info("Starting LearNexus AI application")
    app = create_app()

    # Start background daily scraping (daemon so it stops when Flask stops)
    scraper_thread = threading.Thread(target=_start_daily_scheduler, daemon=True)
    scraper_thread.start()
    logger.info("[Scheduler] Daily scraping thread started (first run in 30 s)")

    logger.info("Available routes:")
    for rule in app.url_map.iter_rules():
        logger.info(f"Route: {rule}, Methods: {rule.methods}")

    app.run(
        host='0.0.0.0',
        port=8000,
        debug=False,   # debug=True spawns a reloader which duplicates threads
        threaded=True
    )
