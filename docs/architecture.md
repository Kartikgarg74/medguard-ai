# MedGuard AI — Architecture Document

**Multi-Agent Medicine Price Compliance System | ET AI Hackathon 2026 (PS5)**

---

## 1. Agent Roles

| Agent | Role | Model | Input | Output |
|-------|------|-------|-------|--------|
| **Scraper Agent** | Collects NPPA ceiling prices + retail prices from 4 pharmacy platforms | None (deterministic) | Medicine names, URLs | Price records in DB |
| **Compliance Checker Agent** | Verifies prices against DPCO 2013 rules. LLM for edge cases only. | Groq Llama 3.1 8B (classification) | Price records + ceiling data | Compliance verdicts + severity |
| **Reporter Agent** | Generates HTML compliance reports with LLM narratives | Groq Llama 3.3 70B (narrative) | Violation data | HTML reports + PDF |
| **Alert Agent** | Routes violation alerts by severity to Telegram/email | None (rule-based routing) | Violations | Telegram messages |

## 2. Agent Communication Flow

```
[Pipeline Orchestrator]
    |
    |--- trigger ---> [Scraper Agent]
    |                      |
    |                      | publishes: "scrape.complete"
    |                      v
    |               [Message Bus (asyncio Queue)]
    |                      |
    |                      | subscribes: "scrape.complete"
    |                      v
    |--- trigger ---> [Compliance Checker Agent]
    |                      |
    |                      | publishes: "compliance.complete"
    |                      v
    |               [Message Bus]
    |                      |
    |--- trigger ---> [Reporter Agent]
    |                      |
    |                      | publishes: "report.ready"
    |                      v
    |--- trigger ---> [Alert Agent]
                           |
                           | sends Telegram alerts (critical/high severity)
```

**Communication Protocol:** In-process asyncio pub/sub message bus with topic-based routing. Each pipeline run shares a correlation ID for end-to-end tracing.

## 3. Tool Integrations

| Tool | Purpose | Integration Method |
|------|---------|-------------------|
| **Groq API** | LLM inference (Llama 3.1 8B + 3.3 70B) | REST API via groq Python SDK |
| **Playwright** | JS-rendered pharmacy scraping (1mg, PharmEasy, Netmeds, Apollo) | Headless Chromium with stealth mode |
| **httpx + BeautifulSoup** | NPPA Pharma Sahi Daam scraping | ASP.NET form POST + HTML parsing |
| **SQLite** | Persistent storage (medicines, prices, violations, audit) | SQLAlchemy ORM |
| **Redis** | Caching (price data TTL) + message queue | redis-py |
| **Telegram Bot API** | Violation alerts | python-telegram-bot |
| **rapidfuzz** | Fuzzy medicine name matching (scraped -> catalog) | Token sort ratio, threshold 70% |
| **Jinja2** | HTML report template rendering | Template inheritance |
| **APScheduler** | Recurring pipeline execution | Cron + interval triggers |

## 4. Error Handling & Recovery

| Error Scenario | Handling Strategy |
|----------------|-------------------|
| **Pharmacy website blocks scraper** | 3 retries with exponential backoff (2s/4s/8s). Stealth mode with UA rotation. If all retries fail, skip platform, continue with others. |
| **NPPA website down** | Fallback to `data/seed/nppa_ceiling_prices.json` (50 pre-cached ceiling prices). Log warning. |
| **Groq API rate limit** | Daily quota tracking (14,400 req/day). If limit hit, skip LLM edge cases — rule engine handles all checks deterministically. |
| **Groq API timeout** | 3 retries with backoff. If all fail, mark as REVIEW_NEEDED (not silent failure). |
| **Fuzzy match below threshold** | Create new medicine entry in catalog. Flag for manual review. |
| **LLM returns invalid JSON** | JSON schema validation. If invalid, fallback to REVIEW_NEEDED verdict. Never crash. |
| **Prompt injection attempt** | 14-pattern regex detection. Reject input before it reaches LLM. Log security event. |
| **Pipeline stage failure** | Each stage is independent. If compliance fails, scraper data is still saved. Pipeline logs error + continues to next viable stage. |
| **Audit chain tampering** | SHA-256 chain verified on every startup. Broken chain triggers WARNING log. Chain integrity exposed via /api/audit/verify endpoint. |

## 5. Data Flow Diagram

```
[NPPA Website] --> [httpx POST] --> [HTML Parser] --> [ceiling_prices table]
                                                              |
[1mg]        --> [Playwright] --+                             |
[PharmEasy]  --> [Playwright] --+--> [Fuzzy Match] --> [retail_prices table]
[Netmeds]    --> [Playwright] --+        |                    |
[Apollo]     --> [Playwright] --+        v                    v
                              [medicines table]    [compliance_checks table]
                                                          |
                                                          v
                                                   [reports table]
                                                          |
                                                          v
                                                   [alerts table] --> [Telegram]

              All operations logged to [audit_log table] with SHA-256 chain
```

## 6. Security Architecture

- **LLM Guardrail:** Rule engine always runs first. LLM cannot override a VIOLATION verdict.
- **Prompt Injection:** 14-pattern regex guard including MedGuard-specific patterns.
- **Audit Trail:** Immutable SHA-256 chained log with tamper detection.
- **Encryption:** Fernet (AES-128-CBC + HMAC) for sensitive data at rest.
- **Input Sanitization:** Length limits, control char removal, injection rejection.
- **Error Sanitization:** API keys and file paths stripped from all error messages.
