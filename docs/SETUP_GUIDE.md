# ROAS Optimization Engine — Setup Guide

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    ROAS ENGINE                          │
│                                                         │
│  ┌─────────┐  ┌──────────┐  ┌─────────────────────┐   │
│  │ Google   │  │ Meta     │  │ Google Search       │   │
│  │ Ads API  │  │ Mktg API │  │ Console API         │   │
│  └────┬─────┘  └────┬─────┘  └──────────┬──────────┘   │
│       │              │                    │              │
│  ┌────▼──────────────▼────────────────────▼──────────┐  │
│  │           Unified Data Layer                      │  │
│  │     (Normalized campaigns, ads, keywords)         │  │
│  └────────────────────┬──────────────────────────────┘  │
│                       │                                  │
│  ┌────────────────────▼──────────────────────────────┐  │
│  │           Decision Engine (Brain)                 │  │
│  │                                                    │  │
│  │  ┌──────────────┐  ┌────────────────────────────┐ │  │
│  │  │ ROAS         │  │ Cross-Platform Budget      │ │  │
│  │  │ Optimizer    │  │ Allocator                  │ │  │
│  │  └──────────────┘  └────────────────────────────┘ │  │
│  │  ┌──────────────┐  ┌────────────────────────────┐ │  │
│  │  │ SEO          │  │ GEO                        │ │  │
│  │  │ Analyzer     │  │ Optimizer                  │ │  │
│  │  └──────────────┘  └────────────────────────────┘ │  │
│  └────────────────────┬──────────────────────────────┘  │
│                       │                                  │
│  ┌────────────────────▼──────────────────────────────┐  │
│  │           Scheduler (Orchestrator)                │  │
│  │  • Optimization cycle: every 60 min               │  │
│  │  • GEO optimization: every 6 hours                │  │
│  │  • SEO audit: daily                               │  │
│  │  • Anomaly monitor: every 15 min                  │  │
│  │  • Daily report: 8 AM                             │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │  FastAPI REST API  ←→  React Dashboard            │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- Google Ads API developer token
- Meta Marketing API app credentials
- Google Search Console service account

---

## Step 1: API Credentials Setup

### Google Ads
1. Go to https://ads.google.com/home/tools/manager-accounts/
2. Create a Manager Account (MCC) if you don't have one
3. Apply for API access: https://developers.google.com/google-ads/api/docs/get-started/dev-token
4. Create OAuth2 credentials in Google Cloud Console
5. Generate a refresh token using the OAuth2 playground
6. Note your Customer ID (10-digit number without dashes)

### Meta Marketing API
1. Go to https://developers.facebook.com/
2. Create an app with "Marketing API" product
3. Generate a long-lived access token (60-day)
4. Note your Ad Account ID (numbers only, no `act_` prefix)
5. For production, set up token refresh automation

### Google Search Console
1. Go to https://console.cloud.google.com/iam-admin/serviceaccounts
2. Create a service account
3. Download the JSON key file
4. Add the service account email as a user in Search Console
5. Grant "Full" permission level

---

## Step 2: Local Development

```bash
# Clone and setup
cd roas-engine

# Copy environment config
cp .env.example .env
# Edit .env with your credentials (see above)

# Start infrastructure
docker compose up -d postgres redis

# Install Python dependencies
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Run the engine
uvicorn app.main:app --reload --port 8000

# In another terminal — start the dashboard
cd frontend
npm install
npm run dev
```

Dashboard: http://localhost:5173
API docs: http://localhost:8000/docs

---

## Step 3: Docker Deployment

```bash
# Build and run everything
docker compose up -d --build

# Check logs
docker compose logs -f backend
```

Dashboard: http://localhost:3000
API: http://localhost:8000

---

## Step 4: GCP Cloud Deployment

```bash
# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Build and push images
gcloud builds submit --tag asia-southeast1-docker.pkg.dev/YOUR_PROJECT/roas-engine/backend ./
gcloud builds submit --tag asia-southeast1-docker.pkg.dev/YOUR_PROJECT/roas-engine/frontend ./

# Deploy with Terraform
cd infra/terraform
terraform init
terraform plan -var="project_id=YOUR_PROJECT" -var="db_password=SECURE_PASSWORD"
terraform apply -var="project_id=YOUR_PROJECT" -var="db_password=SECURE_PASSWORD"
```

---

## How the Engine Works

### Optimization Cycle (Every 60 Minutes)
1. **SYNC** — Pulls latest campaign data from Google Ads and Meta Ads
2. **ANOMALY CHECK** — Detects spending anomalies or critical ROAS drops
3. **SCORE** — Every campaign gets a composite score based on:
   - ROAS performance (35% weight in balanced mode)
   - Efficiency (CPA + conversion rate) (25%)
   - Conversion volume (20%)
   - Trend direction (20%)
4. **DECIDE** — High-confidence actions are generated:
   - Scale winners (increase budget up to 20%/day)
   - Cut underperformers (decrease budget)
   - Pause critically low ROAS campaigns
5. **CROSS-PLATFORM REALLOCATION** — Shifts budget toward the platform delivering better ROAS
6. **EXECUTE** — Actions are applied via platform APIs
7. **LOG + ALERT** — Everything is recorded and Slack/email notifications sent

### Guardrails (Safety Nets)
- Max 20% budget change per day per campaign
- Max 15% bid change per day
- Hard cap on total daily spend ($10,000 default)
- Emergency auto-pause if ROAS drops below 0.5x
- Anomaly detection for spending spikes (200%+ of expected)
- Minimum confidence threshold (75%) before any action
- Minimum 10 conversions before making decisions

### SEO-SEM Alignment
The SEO Analyzer runs daily to:
- Find keywords ranking organically in top 3 where you're still paying for ads → reduce paid spend
- Find high-converting paid keywords with no organic presence → create content
- Detect keyword cannibalization across pages
- Identify quick wins (pages ranking #4-20 that could be pushed higher)

### GEO Optimization
Every 6 hours, the GEO Optimizer:
- Aggregates performance by country/region across both platforms
- Increases bid modifiers for high-ROAS regions
- Decreases bid modifiers for underperforming regions
- Cross-references with organic search geo data

---

## Configuration Reference

| Parameter | Default | Description |
|-----------|---------|-------------|
| `OPTIMIZATION_MODE` | `balanced` | `aggressive`, `balanced`, or `conservative` |
| `TARGET_ROAS` | `4.0` | Target return on ad spend |
| `MIN_ROAS_THRESHOLD` | `1.5` | Campaigns below this are cut |
| `MAX_DAILY_BUDGET_CHANGE_PCT` | `0.20` | Max 20% budget change/day |
| `CONFIDENCE_THRESHOLD` | `0.75` | Min confidence to auto-act |
| `LOOKBACK_DAYS` | `14` | Data window for decisions |
| `MAX_TOTAL_DAILY_BUDGET` | `10000` | Hard cap across all platforms |
| `EMERGENCY_STOP_ROAS_BELOW` | `0.5` | Kill everything threshold |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Engine status |
| GET | `/api/v1/snapshot` | Current performance |
| GET | `/api/v1/campaigns` | All campaigns |
| GET | `/api/v1/platform-summary` | Per-platform stats |
| GET | `/api/v1/actions` | Action history |
| GET | `/api/v1/seo/keywords` | SEO keywords |
| GET | `/api/v1/seo/pages` | SEO page performance |
| GET | `/api/v1/geo/performance` | GEO analysis |
| POST | `/api/v1/optimize/run` | Trigger optimization |
| POST | `/api/v1/campaigns/{platform}/{id}/pause` | Manual pause |
| POST | `/api/v1/campaigns/{platform}/{id}/enable` | Manual enable |
| POST | `/api/v1/campaigns/{platform}/{id}/budget` | Manual budget |
| GET | `/api/v1/config` | Engine config |
