# LearNexus — Project Overview

---

## Problem

IT freshers and university students struggle to:
- Choose the right degree or career path
- Know which modules and topics to focus on
- Stay updated with real-world tech industry trends
- Understand which skills are actually in demand by employers

---

## Solution

**LearNexus** is an AI-powered learning and career guidance platform that:
- Uses a chatbot (LearNexus AI) to guide students through degree and course selection
- Tracks module and topic progress in a knowledge graph
- Recommends relevant jobs and certifications based on the student's skill gaps
- Delivers daily tech news linked directly to their enrolled modules
- Sends WhatsApp alerts to keep students engaged and on track

---

## Objectives

1. Recommend the most suitable IT degree based on student interests and skills
2. Track individual learning progress across modules and topics
3. Match student skills against real-world job requirements
4. Recommend professional certifications to bridge skill gaps
5. Aggregate and deliver relevant tech industry news daily
6. Re-engage at-risk students via automated WhatsApp notifications

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, React, TailwindCSS, Framer Motion |
| Backend | Python, Flask |
| Database | Neo4j (Graph Database) |
| AI / NLP | Google Gemini API, SentenceTransformers (`all-MiniLM-L6-v2`) |
| Authentication | JWT, Google OAuth |
| Notifications | Twilio (WhatsApp), SMTP (Email) |
| Embeddings | Neo4j Vector Index + Cosine Similarity |
| Scraping | BeautifulSoup, Requests, Dev.to / Medium RSS |

---

## Key Achievements

- **AI Degree Advisor** — Conversational chatbot that recommends degrees using semantic search on a Neo4j knowledge graph
- **Real-time Progress Tracking** — Students can see topic/module completion percentages across their enrolled course
- **Career Intelligence Dashboard** — Automatically matches student skills to live job market demands and suggests certifications
- **Tech News Pipeline** — Daily automated scraper that categorises articles across 17 tech categories and links them to enrolled modules
- **Anti-Abandonment Engine** — Detects at-risk students and sends personalised WhatsApp nudges via Twilio
- **Knowledge Graph** — Neo4j graph connecting Users, Courses, Modules, Topics, Skills, Jobs, Articles, and Certifications for powerful semantic recommendations
- **Google OAuth + OTP Security** — Secure login with Google sign-in and OTP-based email/WhatsApp verification for profile changes

---

## Color Theme

| Role | Name | Hex |
|---|---|---|
| 🟦 Primary | Deep Navy Blue | `#1A237E` |
| 🔵 Secondary | Bright Blue | `#2979FF` |
| 🟢 Accent | Teal Green | `#00BFA5` |
| ✅ Success | Green | `#4CAF50` |
| ⚠️ Warning | Amber | `#FFC107` |
| ❌ Error | Red | `#F44336` |
| ⬜ Background | Light Grey | `#F8F9FA` |
| 🌙 Dark Background | Dark Slate | `#0F172A` |

> Font: **Inter** (sans-serif)
