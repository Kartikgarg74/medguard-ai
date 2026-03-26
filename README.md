# MedGuard AI

> Multi-Agent AI system that monitors medicine prices across Indian online pharmacies and flags DPCO 2013 compliance violations in real-time.

## Problem Statement (PS5)

Domain-Specialized AI Agents with Compliance Guardrails — ET AI Hackathon 2026

## Quick Start

```bash
# Clone
git clone https://github.com/Kartikgarg74/medguard-ai.git
cd medguard-ai

# Setup backend
cd backend
pip install -r requirements.txt
playwright install chromium

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run
uvicorn src.main:app --reload
```

## Status

Work in progress. See feature branches for development progress.
