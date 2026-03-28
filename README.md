# MedGuard AI

**Multi-Agent AI system that monitors medicine prices across Indian online pharmacies and flags DPCO 2013 compliance violations in real-time.**

> ET AI Hackathon 2026 | Problem Statement #5: Domain-Specialized AI Agents with Compliance Guardrails
> Hiring Partner: Avataar.ai | Hackathon Partner: Unstop

---

## Problem

India has **Rs 10,013 crore** in detected pharmaceutical overcharging since NPPA inception, with only **14.8% recovered** (Rs 1,487 crore). The government's app (Pharma Sahi Daam) has just 220K downloads and is a passive lookup tool. **Zero startups or tools exist for automated DPCO compliance monitoring.**

Razorpay Fix My Itch Score: **91** (highest validated problem) -- "Why do medicine prices vary 30-50% across pharmacy chains for the exact same drug?"

## Solution

MedGuard AI deploys **4 specialized AI agents** that autonomously:

1. **Scrape** ceiling prices from NPPA + retail prices from 1mg, PharmEasy, Netmeds, Apollo Pharmacy
2. **Check** every price against DPCO 2013 rules (deterministic engine + LLM for edge cases)
3. **Report** violations with DPCO section citations and LLM-generated narratives
4. **Alert** stakeholders via Telegram with severity-based routing

## Architecture

```
                        MEDGUARD AI SYSTEM
  +----------------------------------------------------------+
  |                                                          |
  |   [NPPA]  [1mg]  [PharmEasy]  [Netmeds]  [Apollo]       |
  |      |       |        |           |          |           |
  |      v       v        v           v          v           |
  |   +--------------------------------------------------+   |
  |   |           SCRAPER AGENT (Playwright)             |   |
  |   |  NPPA ceiling prices + pharmacy retail prices    |   |
  |   +------------------------+-------------------------+   |
  |                            |                             |
  |                            v                             |
  |   +--------------------------------------------------+   |
  |   |         COMPLIANCE CHECKER AGENT                 |   |
  |   |  DPCO rules engine (deterministic)               |   |
  |   |  + Groq Llama 3.1 8B (edge cases only)          |   |
  |   |  Guardrail: LLM cannot override rule violations  |   |
  |   +------------------------+-------------------------+   |
  |                            |                             |
  |                            v                             |
  |   +--------------------------------------------------+   |
  |   |           REPORTER AGENT                         |   |
  |   |  HTML reports with Groq Llama 3.3 70B narrative  |   |
  |   |  DPCO section citations in every violation       |   |
  |   +------------------------+-------------------------+   |
  |                            |                             |
  |                            v                             |
  |   +--------------------------------------------------+   |
  |   |            ALERT AGENT                           |   |
  |   |  Telegram alerts by severity (critical/high)     |   |
  |   |  24h dedup + HMAC-signed acknowledge buttons     |   |
  |   +--------------------------------------------------+   |
  |                                                          |
  |   [SQLite DB]  [Redis Cache]  [SHA-256 Audit Chain]      |
  |   [Next.js Dashboard]  [FastAPI REST API]                |
  +----------------------------------------------------------+
```

## Compliance Guardrails

| Guardrail | Implementation |
|-----------|---------------|
| Deterministic first | DPCO rules engine runs before any LLM call |
| LLM restricted | Only invoked for REVIEW_NEEDED cases (ambiguous matches, combination drugs) |
| Cannot override | LLM verdict cannot downgrade a rule-engine VIOLATION |
| Output validated | JSON schema validation on every LLM response |
| Prompt injection | 14-pattern detection including MedGuard-specific attacks |
| Audit trail | SHA-256 chained immutable log, every decision traced with agent + model attribution |
| Input sanitization | Length limits, control char removal, injection rejection |
| Error sanitization | API keys, file paths, tokens stripped from all logs |

## DPCO 2013 Rules Encoded

| Rule | DPCO Paragraph | Implementation |
|------|:-:|----------------|
| Scheduled drug ceiling price | Para 4-7 | Retail price vs NPPA ceiling + WPI adjustment (1.74028%) |
| Non-scheduled 10% annual cap | Para 20 | Current vs previous year price comparison |
| Overcharge + interest | Para 15 | 15% p.a. interest on overcharged amount |
| Retailer responsibility | Para 16 | Cannot sell above notified price |
| Severity classification | -- | Critical (>50%), High (20-50%), Medium (5-20%), Low (<5%) |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+ / FastAPI |
| LLM | Groq free tier (Llama 3.1 8B + Llama 3.3 70B) |
| Scraping | Playwright (JS-rendered pharmacies) + httpx (NPPA) |
| Database | SQLite via SQLAlchemy |
| Matching | rapidfuzz (fuzzy medicine name matching) |
| Frontend | Next.js 15 / React 19 / Recharts / Tailwind CSS |
| Alerts | Telegram Bot API |
| Orchestration | asyncio message bus + APScheduler |
| Security | Fernet encryption, prompt injection guard, SHA-256 audit chain |

## Quick Start

```bash
# Clone
git clone https://github.com/Kartikgarg74/medguard-ai.git
cd medguard-ai

# Backend
cd backend
pip install -r requirements.txt
playwright install chromium
cp .env.example .env  # Edit with your GROQ_API_KEY
uvicorn src.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev

# Open http://localhost:3000
```

## Docker

```bash
docker compose up -d
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | System health check |
| GET | `/api/medicines?search=` | Search medicines |
| GET | `/api/medicines/{id}` | Medicine detail + price comparison |
| GET | `/api/violations` | List violations (filterable) |
| GET | `/api/violations/stats` | Aggregated violation stats |
| GET | `/api/dashboard/stats` | Dashboard KPIs |
| GET | `/api/dashboard/top-violators` | Top 10 overpriced medicines |
| GET | `/api/reports` | Generated reports |
| GET | `/api/reports/{id}/view` | View HTML report |
| POST | `/api/scraper/trigger` | Trigger pipeline scan |
| GET | `/api/scraper/status` | Pipeline status |
| GET | `/api/audit/verify` | Verify audit chain integrity |
| GET | `/api/audit/log` | Query audit log |

## Data Sources

| Source | Type | Purpose |
|--------|------|---------|
| NPPA Pharma Sahi Daam | Real-time scrape | Ceiling prices for DPCO-scheduled drugs |
| 1mg | Playwright scrape | Retail prices + discounts |
| PharmEasy | Playwright scrape | Retail prices + discounts |
| Netmeds | Playwright scrape | Retail prices + discounts |
| Apollo Pharmacy | Playwright scrape (stealth) | Retail prices + discounts |
| GitHub Indian Medicine Dataset | CSV seed | 253K medicine reference catalog |

**No Kaggle datasets.** All pricing data scraped from live sources.

## Test Coverage

```
144 tests passing
- Unit: config, cache, models, audit chain, DPCO rules, scrapers, reporters, alerts, security
- Integration: all API endpoints with seeded data
- Tamper detection: audit chain integrity verification
```

## Evaluation Criteria Mapping

| Criteria | How Addressed |
|----------|---------------|
| **Domain Depth** | DPCO 2013 rules engine with WPI adjustment, Para 15 interest calc, NLEM-aware, 928+ formulations |
| **Compliance Guardrails** | Deterministic rules first, LLM restricted to REVIEW_NEEDED, output validation, prompt injection guard |
| **Edge Cases** | Combination drugs, brand-generic matching, pack size normalization, fuzzy matching (rapidfuzz) |
| **Full Task Completion** | End-to-end: scrape -> check -> report -> alert (4-stage autonomous pipeline) |
| **Auditability** | SHA-256 chained immutable log, every decision traced with agent + model + timestamp |

## Impact Model

```
Rs 8,526 crore in unrecovered pharmaceutical overcharging.
MedGuard detects violations in 6 hours instead of 3-5 years.
Operating cost: Rs 6 lakh/year vs Rs 16 crore/year for manual PMRUs.
If MedGuard catches 1% of outstanding overcharging = Rs 85 crore saved.
```

## Team

**Kartik Garg** | USICT, GGSIPU, Delhi

## License

MIT
