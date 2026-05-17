import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Messages sent to the user at each inactivity milestone (days)
_USER_MSGS = {
    3: lambda n: (
        f"👋 *Hey {n}!*\n\n"
        f"We haven't seen you on LearNexus for 3 days — we miss you! 😊\n\n"
        f"Your learning journey is still waiting for you. Even just 15 minutes today "
        f"can keep the momentum going! 💪\n\n"
        f"📚 Come back and continue where you left off!"
    ),
    7: lambda n: (
        f"🌟 *{n}, it's been a whole week!*\n\n"
        f"Seven days without LearNexus — your modules are missing you! 😄\n\n"
        f"Don't let your progress fade away. You've worked hard to get this far, "
        f"and it would be a shame to stop now.\n\n"
        f"🎯 Jump back in today — your goals are still within reach!"
    ),
    14: lambda n: (
        f"💡 *{n}, your learning journey is on pause...*\n\n"
        f"It's been two weeks since your last visit to LearNexus.\n\n"
        f"Remember the goals that brought you here? They haven't changed — "
        f"and neither has your potential! 🚀\n\n"
        f"Come back today and reignite that spark. We're rooting for you! 🎓"
    ),
    30: lambda n: (
        f"🎓 *{n}, we haven't forgotten about you!*\n\n"
        f"It's been a whole month since your last login — and we still believe in you.\n\n"
        f"Everything is right where you left it: your progress, your courses, your goals. 📖\n\n"
        f"It's never too late to restart. Take one small step today — "
        f"that's all it takes to get back on track.\n\n"
        f"_We'll be here cheering you on!_ ❤️\n\n"
        f"— The LearNexus Team 🎓"
    ),
}

# Message sent to parent at the 7-day milestone
def _parent_msg(student_name: str, days: int) -> str:
    return (
        f"👋 *Hello from LearNexus!*\n\n"
        f"We wanted to let you know that *{student_name}* hasn't logged in to "
        f"their LearNexus learning platform for *{days} days*.\n\n"
        f"LearNexus is their personalised university learning companion — "
        f"a gentle nudge or some encouragement from you might be just what they need! 😊\n\n"
        f"_LearNexus — Personalized Learning Platform_ 🎓"
    )


def _check_inactivity():
    """Called by APScheduler daily at 09:00 — sends WhatsApp reminders to inactive users."""
    try:
        from neo4j import GraphDatabase
        from api.services.whatsapp_service import send_whatsapp

        driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "LearNexus1212"))
        )

        now = datetime.now(timezone.utc)

        with driver.session() as session:
            rows = session.run("""
                MATCH (s:Student)
                WHERE s.last_login IS NOT NULL AND s.whatsapp_number IS NOT NULL
                RETURN s.name AS name,
                       s.whatsapp_number AS phone,
                       s.parent_number   AS parent,
                       s.last_login      AS last_login
            """)

            for r in rows:
                try:
                    last = r["last_login"]
                    if hasattr(last, "to_native"):
                        last = last.to_native()
                    if last.tzinfo is None:
                        last = last.replace(tzinfo=timezone.utc)

                    days = (now - last).days
                    first_name = (r["name"] or "there").split()[0]

                    if days in _USER_MSGS:
                        send_whatsapp(r["phone"], _USER_MSGS[days](first_name))
                        logger.info(f"Inactivity msg ({days}d) → {r['phone']}")

                    if days == 7 and r.get("parent"):
                        send_whatsapp(r["parent"], _parent_msg(r["name"], days))
                        logger.info(f"Parent notification (7d) → {r['parent']}")

                except Exception as e:
                    logger.error(f"Inactivity row error: {e}")

        driver.close()

    except Exception as e:
        logger.error(f"Inactivity check failed: {e}")


def _run_article_pipeline():
    """Scrape fresh tech articles and store in Neo4j with cover images."""
    try:
        import sys
        import os
        pipeline_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models', 'pipeline'))
        if pipeline_dir not in sys.path:
            sys.path.insert(0, pipeline_dir)

        from models.pipeline.technology_pipeline import TechnologyPipeline
        logger.info("Article pipeline starting — scraping new articles...")
        pipeline = TechnologyPipeline()
        pipeline.process_new_articles()
        logger.info(f"Article pipeline finished — {pipeline.statistics['articles_processed']} new articles processed")
    except Exception as e:
        logger.error(f"Article pipeline failed: {e}")


def start_scheduler():
    """Start background scheduler. Call once from app factory."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from datetime import datetime, timedelta

        scheduler = BackgroundScheduler()

        # Inactivity check — daily at 09:00
        scheduler.add_job(_check_inactivity, "cron", hour=9, minute=0, id="inactivity_check")

        # Article pipeline — daily at 06:00
        scheduler.add_job(_run_article_pipeline, "cron", hour=6, minute=0, id="article_pipeline")

        # Also run the pipeline once on startup (30s delay so the app boots first)
        scheduler.add_job(
            _run_article_pipeline,
            "date",
            run_date=datetime.now() + timedelta(seconds=30),
            id="article_pipeline_startup",
        )

        scheduler.start()
        logger.info("Scheduler started — inactivity daily 09:00, articles daily 06:00 + on startup")
        return scheduler
    except ImportError:
        logger.warning("apscheduler not installed — run: pip install apscheduler")
    except Exception as e:
        logger.error(f"Scheduler init error: {e}")
    return None
