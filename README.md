# LearNexus: AI-Powered Career Intelligence & Guidance Platform

LearNexus is an end-to-end AI-driven learning and career progression platform tailored for IT students and freshers. It dynamically combines personalized degree tracking, real-time tech industry news, and career intelligence (job & certification recommendations) powered by a robust Neo4j knowledge graph and Large Language Models.

## 🌟 Key Features

### 1. LearNexus AI Assistant
A context-aware AI chatbot that acts as a personalized academic and career advisor. It guides users through course selection, answers module-specific questions, and provides tailored learning paths based on their current progress and skill profile.
*   **Semantic Intent Thresholding:** The AI uses a finely-tuned cosine similarity threshold (0.3) against Neo4j embeddings to distinguish between casual chatter ("hi") and genuine academic intent ("I want to study data science"). This prevents premature degree recommendations while maintaining natural conversational fluidity.
*   **Session Memory:** Supports multi-turn conversations via a configurable `session_id`. Each browser tab or user gets a persistent dialogue context, so follow-up questions like *"Tell me more about the 2nd one"* work naturally.
*   **Stable API Contract:** The `/chat` endpoint returns a consistent `{"status": "success", "message": "..."}` format. All requests and responses are logged with `logger.info()` including session ID for production tracing.

### 2. Career Intelligence & Industry Alignment
Evaluates a user's acquired skills against real-world job market demands. 
*   **Industry Job Scrapes**: The system continuously scrapes major job boards to identify trending roles and required technical skills.
*   **Industry Requirements**: Matches the user's current progress against the scraped industry requirements to identify skill gaps.
*   **Certifications**: Automatically scrapes and recommends recognized professional certifications (e.g., AWS, CompTIA, Cisco) that bridge the user's specific skill gaps, making them job-ready.

### 3. Dynamic Tech Radar (News Intelligence)
*   **Daily Automated Scrape**: An automated background pipeline runs daily to scrape technology articles, news, and tutorials from Dev.to, Medium RSS, and Google News.
*   **Auto-Categorization & Linking**: The AI processes the full HTML content, strips noise, auto-categorizes articles into specific tech fields (e.g., AI, Web Dev, DevOps), and semantically links them directly to the user's enrolled academic modules in the Knowledge Graph.
*   **17-Category Keyword Engine**: The `categorize_article()` function in `deepseel2.py` scans each article's title, description, and tags against ~200+ keywords across 17 categories (`ai`, `python`, `webdev`, `devops`, `cloud`, `docker`, `cybersecurity`, `database`, `datascience`, `llm`, `networking`, `testing`, `softwareengineering`, `mobile`, `opensource`, `blockchain`, `career`) to ensure accurate frontend filter placement.
*   **World Trending Widget**: The homepage "Tech Radar" displays real-time trending articles from [dev.to](https://dev.to) (top reactions, 7-day window). Results are cached server-side for 1 hour with a graceful fallback if dev.to is unreachable.
*   **Premium Article Cards**: The "Course News" (Dashboard) and "Related Articles" (Module page) sidebars display articles with cover image thumbnails, gradient tag badges, hover zoom effects, and clean text previews.

### 4. Anti-Abandonment Engine & WhatsApp Notifications
To ensure high student engagement and completion rates, LearNexus features a proactive retention system:
*   **Anti-Abandonment Engine**: Analyzes user activity, topic completion patterns, and engagement metrics to identify students who are at risk of dropping out or falling behind.
*   **WhatsApp Notifications**: Automatically triggers personalized WhatsApp alerts (via Twilio integration) to re-engage students. These messages provide motivational nudges, recommend highly relevant "Course News" articles, and suggest bite-sized topics to get them back on track.
*   **Optional WhatsApp Onboarding**: WhatsApp linking is presented during signup but is **not mandatory**. Users can click "Skip for now" and link their number later from **Profile → Security → Add/Change WhatsApp Number**. The frontend UI dynamically detects if a user has a linked number and adjusts the security prompts accordingly.

### 5. Knowledge Graph Architecture
At the core of LearNexus is a Neo4j graph database that maps complex relationships between `Users`, `Courses`, `Modules`, `Topics`, `Skills`, `Articles`, `JobRoles`, and `Certifications`. This enables powerful semantic querying and highly accurate, context-aware recommendations.

---

## 🏗️ System Architecture & Workflow

The platform is split into a Python/Flask Backend (this repository) and a Next.js/React Frontend.

### Backend Overview
*   **Framework:** Python, Flask
*   **Database:** Neo4j (Graph Database)
*   **AI/ML:** SentenceTransformers (`all-MiniLM-L6-v2`) for embeddings, Google Gemini / XAI for generative AI capabilities.
*   **Automation:** Background scheduling (APScheduler / threading) for continuous daily data ingestion and notification dispatch.
*   **Communication:** Twilio API for WhatsApp messaging.

### Automated Data Pipelines (The "Brain")
1.  **Tech News Pipeline (`models/pipeline/technology_pipeline.py`):**
    *   **Scraping:** Fetches articles daily.
    *   **Processing:** Extracts full HTML content and creates a clean `short_description`.
    *   **AI Categorization:** Scans content against predefined keyword mappings to auto-tag articles.
    *   **Embedding & Deduplication:** Generates vector embeddings for semantic similarity. Deduplicates content using content hashing and URL tracking.
    *   **Graph Linking:** Computes cosine similarity between article embeddings and module embeddings to automatically map news to relevant academic modules (`[:RELATED_TO]`).
2.  **Job & Certification Pipelines:** 
    *   Continuously scrapes external job boards and certification providers. It extracts required skills via NLP, deduplicates entries, and integrates them into the Neo4j graph to power the Career Intelligence dashboard.

### API & Routing Layer
*   **`tech_updates_for_fe.py` / `tech_updates_module.py`:** Serves categorized news to the frontend with a two-tier HTML sanitization strategy — backend strips tags and generates a clean `short_description` (≤300 chars), while frontend `stripHtml()` helpers act as a safety net.
*   **`career_intelligence.py` / `job_recommendations.py`:** Executes complex Cypher queries to match a user's completed topic skills against job/certification requirements.
*   **`module_chat.py`:** Handles the LearNexus AI conversation logic, maintaining context per module.
*   **`auth.py` / `profile.py`:** Robust JWT-based authentication layer. Features safe error handling (e.g., catching missing password hashes for OAuth Google Logins) and secure OTP verification via Email and Green API (WhatsApp).
*   **`new_chat_interface.py`:** Session-aware chat API with `session_id` passthrough for conversation memory and structured debug logging.

---

## 🚀 Getting Started

### Prerequisites
*   Python 3.9+
*   Neo4j Desktop or Server (running locally on `bolt://localhost:7687` or configured via env)
*   API Keys: Google Gemini API key (and optionally XAI API key), Twilio API Keys (for WhatsApp)

### Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/sasindu26/LearNexus.git
   cd LearNexus
   ```

2. **Set Up a Virtual Environment**
   ```bash
   python -m venv .venv
   
   # Windows
   .venv\Scripts\activate
   
   # macOS/Linux
   source .venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables**
   Create a `.env` file in the root directory:
   ```env
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password
   GEMINI_API_KEY=your_gemini_api_key
   XAI_API_KEY=your_xai_api_key
   TWILIO_ACCOUNT_SID=your_twilio_sid
   TWILIO_AUTH_TOKEN=your_twilio_token
   TWILIO_WHATSAPP_NUMBER=whatsapp:+1234567890
   ```

5. **Run the Backend Server**
   This script initializes the Flask app and starts the background scraping and notification schedulers.
   ```bash
   python run.py
   ```
   *The server will run on `http://0.0.0.0:8000`.*

---

## 📂 Project Structure

```text
LearNexus/
├── api/                      # Flask Application & Routes
│   ├── routes/               # API endpoints (auth, chat, career, tech updates)
│   ├── services/             # Core business logic (embeddings, Neo4j interactions)
│   └── main_app.py           # Flask app factory
├── models/                   # Machine Learning & AI Models
│   ├── pipeline/             # Data ingestion pipelines (Scrapers, Embeddings, Graph updates)
│   └── basic_iomodel/        # Generative AI wrappers (Gemini/XAI)
├── scrapers/                 # Specialized web scraping scripts (Jobs, Certs)
├── scripts/                  # Maintenance and backfill utility scripts
├── data/                     # Raw and processed data dumps (CSV, JSON)
├── requirements.txt          # Python dependencies
└── run.py                    # Main entry point & background scheduler
```

---

## 🔗 Frontend Repository
The user interface for LearNexus is built with Next.js, TailwindCSS, and Framer Motion. 
**Repository:** [LearNexus_frontend](https://github.com/sasindu26/LearNexus_frontend)

---
*Developed by sasindu26.*

