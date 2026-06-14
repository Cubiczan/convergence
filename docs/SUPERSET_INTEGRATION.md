# Apache Superset Integration

## Overview

Apache Superset (73K stars) provides a production-grade analytics layer that replaces the Next.js convergence dashboard with enterprise BI capabilities. Superset offers interactive dashboards, SQL Lab for ad-hoc analysis, and embedded analytics — all connecting directly to the existing PostgreSQL database.

### Why Superset Over Next.js Dashboard

| Capability | Next.js Dashboard | Apache Superset |
|---|---|---|
| **Dashboard Interactivity** | Static React components | Drag-and-drop, filters, drill-down |
| **SQL Ad-Hoc Queries** | None | Full SQL Lab IDE |
| **Embedded Analytics** | Manual iframe | Native SDK with white-labeling |
| **Multi-User Security** | None built-in | Row-level security (RLS) |
| **Export** | None | PDF, CSV, Excel, email |
| **Scheduling** | None | Cron-based email reports |

### Architecture

```
PostgreSQL (Managed)
    ├── Next.js Dashboard (legacy, can be retired)
    └── Apache Superset
        ├── Integration Health Dashboard
        ├── Workstream Status Dashboard
        ├── CHP Decision Pipeline Dashboard
        ├── Risk Registry Dashboard
        └── Synergy Pipeline Dashboard
        └── Embedded SDK → Client Portal
```

## Pre-Built Dashboards

### 1. Integration Health Dashboard

**Purpose**: Real-time convergence score across all workstreams for a deal.

**Charts**:
- Overall convergence gauge (RED/AMBER/GREEN)
- Foundation score trend line
- Active workstreams count
- Decision lock progress (pie chart)

### 2. Workstream Status Dashboard

**Purpose**: Per-workstream breakdown of health, progress, and agent activity.

**Charts**:
- Workstream health matrix (heatmap)
- Agent activity timeline
- Workstream progress bars
- Close/cutover milestone tracker

### 3. CHP Decision Pipeline Dashboard

**Purpose**: Full visibility into decision lifecycle from EXPLORING to LOCKED.

**Charts**:
- Decision funnel (EXPLORING → PROVISIONAL_LOCK → LOCKED)
- Foundation score distribution histogram
- Validation status tracker
- R0 gate pass/fail rate

### 4. Risk Registry Dashboard

**Purpose**: Active risks across all workstreams with severity and mitigation status.

**Charts**:
- Risk severity matrix (impact vs likelihood)
- Risk trend over time
- Top 10 risks table
- Mitigation completion rate gauge

### 5. Synergy Pipeline Dashboard

**Purpose**: Financial synergy tracking with target vs realized values.

**Charts**:
- Synergy pipeline funnel
- Realized vs target bar chart
- Category breakdown (cost, revenue, financial)
- Synergy capture timeline

## SQL Queries

All queries run against the PostgreSQL database backing Convergence.

### Integration Health Dashboard

```sql
-- Overall convergence health by deal
SELECT
    d.deal_name,
    d.deal_type,
    c.overall_health,
    c.foundation_score,
    c.total_workstreams,
    c.active_workstreams,
    c.last_updated
FROM convergence_overview c
JOIN deals d ON c.deal_id = d.id
WHERE d.deal_name = :deal_name;

-- Foundation score trend (daily snapshots)
SELECT
    DATE_TRUNC('day', created_at) AS snapshot_date,
    foundation_score,
    overall_health
FROM convergence_snapshots
WHERE deal_id = :deal_id
ORDER BY created_at;

-- Active decisions count
SELECT
    status,
    COUNT(*) AS count
FROM decisions
WHERE deal_id = :deal_id
GROUP BY status;
```

### Workstream Status Dashboard

```sql
-- Workstream health matrix
SELECT
    w.workstream_type,
    w.name,
    w.health_status,
    w.progress_pct,
    w.last_analyzed,
    (SELECT COUNT(*) FROM agents a WHERE a.workstream_id = w.id) AS agent_count
FROM workstreams w
WHERE w.deal_id = :deal_id
ORDER BY w.workstream_type;

-- Agent activity log
SELECT
    a.agent_role,
    a.agent_type,
    al.action,
    al.timestamp,
    al.confidence_score
FROM agent_logs al
JOIN agents a ON al.agent_id = a.id
WHERE a.workstream_id = :workstream_id
ORDER BY al.timestamp DESC
LIMIT 50;

-- Workstream milestone tracker
SELECT
    m.milestone_name,
    m.target_date,
    m.status,
    w.name AS workstream_name
FROM milestones m
JOIN workstreams w ON m.workstream_id = w.id
WHERE w.deal_id = :deal_id
ORDER BY m.target_date;
```

### CHP Decision Pipeline Dashboard

```sql
-- Decision funnel status
SELECT
    status,
    COUNT(*) AS total,
    AVG(foundation_score) AS avg_foundation_score,
    AVG(EXTRACT(EPOCH FROM (updated_at - created_at)) / 3600) AS avg_hours_in_status
FROM decisions
WHERE deal_id = :deal_id
GROUP BY status;

-- Foundation score distribution
SELECT
    CASE
        WHEN foundation_score >= 100 THEN '100 (Clean Lock)'
        WHEN foundation_score >= 90 THEN '90-99'
        WHEN foundation_score >= 80 THEN '80-89'
        WHEN foundation_score >= 70 THEN '70-79 (Minimum Threshold)'
        WHEN foundation_score >= 60 THEN '60-69 (Reframe Required)'
        ELSE '<60 (Critical)'
    END AS score_band,
    COUNT(*) AS decision_count
FROM decisions
WHERE deal_id = :deal_id
GROUP BY score_band
ORDER BY MIN(foundation_score) DESC;

-- Validation status
SELECT
    d.decision_name,
    d.status,
    d.foundation_score,
    v.validator_name,
    v.validation_result,
    v.validated_at
FROM decisions d
LEFT JOIN validations v ON d.id = v.decision_id
WHERE d.deal_id = :deal_id;

-- R0 gate pass/fail
SELECT
    gate_name,
    result,
    COUNT(*) AS total,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS pct
FROM r0_gates
WHERE deal_id = :deal_id
GROUP BY gate_name, result;
```

### Risk Registry Dashboard

```sql
-- Risk severity matrix
SELECT
    r.risk_name,
    r.severity,
    r.likelihood,
    r.impact_score,
    r.likelihood_score,
    r.mitigation_status,
    w.name AS workstream_name
FROM risks r
JOIN workstreams w ON r.workstream_id = w.id
WHERE w.deal_id = :deal_id
ORDER BY r.impact_score * r.likelihood_score DESC;

-- Risk trend over time
SELECT
    DATE_TRUNC('week', created_at) AS week,
    COUNT(*) AS new_risks,
    SUM(CASE WHEN mitigation_status = 'resolved' THEN 1 ELSE 0 END) AS resolved
FROM risks r
JOIN workstreams w ON r.workstream_id = w.id
WHERE w.deal_id = :deal_id
GROUP BY week
ORDER BY week;

-- Top 10 risks
SELECT
    r.risk_name,
    r.description,
    r.severity,
    r.impact_score,
    r.likelihood_score,
    r.mitigation_status,
    r.assigned_to
FROM risks r
JOIN workstreams w ON r.workstream_id = w.id
WHERE w.deal_id = :deal_id
ORDER BY (r.impact_score * r.likelihood_score) DESC
LIMIT 10;

-- Mitigation completion rate
SELECT
    COUNT(CASE WHEN mitigation_status = 'resolved' THEN 1 END) AS resolved,
    COUNT(*) AS total,
    ROUND(
        COUNT(CASE WHEN mitigation_status = 'resolved' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0),
        1
    ) AS completion_pct
FROM risks r
JOIN workstreams w ON r.workstream_id = w.id
WHERE w.deal_id = :deal_id;
```

### Synergy Pipeline Dashboard

```sql
-- Synergy pipeline funnel
SELECT
    stage,
    COUNT(*) AS total_synergies,
    SUM(target_value) AS total_target,
    SUM(realized_value) AS total_realized
FROM synergies
WHERE deal_id = :deal_id
GROUP BY stage;

-- Realized vs target by category
SELECT
    category,
    SUM(target_value) AS target,
    SUM(realized_value) AS realized,
    ROUND(SUM(realized_value) / NULLIF(SUM(target_value), 0) * 100, 1) AS realization_pct
FROM synergies
WHERE deal_id = :deal_id
GROUP BY category;

-- Synergy capture timeline
SELECT
    DATE_TRUNC('month', capture_date) AS month,
    SUM(realized_value) AS captured,
    category
FROM synergies
WHERE deal_id = :deal_id
  AND capture_date IS NOT NULL
GROUP BY month, category
ORDER BY month;
```

## Embedded Analytics & White-Labeling

### Superset Embedded SDK

Superset provides a JavaScript SDK for embedding dashboards into client portals:

```html
<script src="https://unpkg.com/@superset-ui/embedded-sdk"></script>
<div id="dashboard-container"></div>
<script>
  SupersetEmbed.init({
    id: "your-dashboard-id",
    supersetUrl: "https://analytics.yourdomain.com",
    supersetDomain: "https://analytics.yourdomain.com",
    mountDirectory: "/static/",
  });
</script>
```

### White-Label Configuration

In `superset_config.py`:

```python
# Branding
APP_NAME = "Convergence Analytics"
LOGO = "/static/logos/convergence-logo.svg"
FAVICON = "/static/logos/favicon.ico"

# Color theme (matches convergence color scheme)
THEME_OVERRIDES = {
    "primaryColor": "#1a1a2e",
    "secondaryColor": "#16213e",
    "successColor": "#0f9b58",
    "warningColor": "#f39c12",
    "dangerColor": "#e74c3c",
}

# Custom CSS for white-labeling
CUSTOM_CSS = """
.embedded-dashboard {
    border: none;
    border-radius: 8px;
}
.navbar-brand {
    font-family: 'Inter', sans-serif;
    font-weight: 600;
}
"""

# Disable Superset branding in embeds
TALISMAN_ENABLED = False
WTF_CSRF_ENABLED = False

# Allow embedding from client domains
HTTP_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "X-CSRFToken",
}
```

### Client Portal Integration

```python
# API endpoint to generate embedded dashboard token
@app.get("/api/v1/clients/{client_id}/dashboard-token")
async def get_dashboard_token(client_id: str):
    """Generate time-limited Superset embedded dashboard token."""
    client = await get_client(client_id)
    token = generate_superset_token(
        client_id=client_id,
        dashboard_ids=client.assigned_dashboards,
        rls_filters={"deal_id": client.active_deals},
        expiry_hours=24
    )
    return {"token": token, "expires_in": 86400}
```

## Row-Level Security (RLS)

### Multi-Deal Security Model

Superset RLS ensures users only see data for deals they're authorized to access.

#### Create Security Roles

```sql
-- Super Admin (sees everything)
INSERT INTO ab_role (name) VALUES ('Convergence Super Admin');

-- Deal Manager (sees assigned deals only)
INSERT INTO ab_role (name) VALUES ('Convergence Deal Manager');

-- Read-Only Analyst (sees assigned deals, no edit)
INSERT INTO ab_role (name) VALUES ('Convergence Analyst');

-- Client User (sees only their deal, embedded only)
INSERT INTO ab_role (name) VALUES ('Convergence Client');
```

#### Row-Level Security Rules

```sql
-- Rule: Deal Manager sees only their assigned deals
INSERT INTO sl_rls (rule_type, clause, database_id)
VALUES (
    'Regular',
    'deal_id IN (SELECT deal_id FROM user_deal_access WHERE user_id = {{ current_user_id() }})',
    (SELECT id FROM dbs WHERE database_name = 'convergence')
);

-- Rule: Analyst sees only published/locked decisions
INSERT INTO sl_rls (rule_type, clause, database_id)
VALUES (
    'Regular',
    'deal_id IN (SELECT deal_id FROM user_deal_access WHERE user_id = {{ current_user_id() }}) AND status IN (''PROVISIONAL_LOCK'', ''LOCKED'')',
    (SELECT id FROM dbs WHERE database_name = 'convergence')
);

-- Rule: Client user sees only their company's deals
INSERT INTO sl_rls (rule_type, clause, database_id)
VALUES (
    'Regular',
    'deal_id IN (SELECT deal_id FROM deals WHERE client_id = {{ current_user_id() }})',
    (SELECT id FROM dbs WHERE database_name = 'convergence')
);
```

#### User-Deal Access Table

```sql
CREATE TABLE user_deal_access (
    user_id INTEGER REFERENCES ab_user(id),
    deal_id INTEGER REFERENCES deals(id),
    access_level VARCHAR(20) DEFAULT 'read',
    granted_at TIMESTAMP DEFAULT NOW(),
    granted_by INTEGER REFERENCES ab_user(id),
    PRIMARY KEY (user_id, deal_id)
);

-- Grant access example
INSERT INTO user_deal_access (user_id, deal_id, access_level)
VALUES (42, 7, 'read');
```

#### Apply RLS to Datasets

In Superset UI or via API:

```python
# Apply RLS filter to dataset
PUT /api/v1/dataset/{dataset_id}
{
    "sql": null,
    "schema": "public",
    "rls": true,
    "rls_filters": [
        {
            "clause": "deal_id IN (SELECT deal_id FROM user_deal_access WHERE user_id = {{ current_user_id() }})",
            "group_key": "deal_access"
        }
    ]
}
```

### Session Variables for Dynamic RLS

```python
# Set session variables per user on login
@app.middleware("http")
async def set_superset_rls(request, call_next):
    if request.url.path.startswith("/superset/"):
        user = get_current_user()
        # Set RLS variables in Superset session
        request.state.superset_rls = {
            "current_user_id": user.id,
            "user_role": user.role,
            "client_id": user.client_id
        }
    return await call_next(request)
```

## Deployment

### Docker Compose

```yaml
# docker-compose.superset.yml
version: "3.8"
services:
  superset:
    image: apache/superset:latest
    ports:
      - "8088:8088"
    environment:
      - SUPERSET_SECRET_KEY=${SUPERSET_SECRET_KEY}
      - DATABASE_URL=postgresql+psycopg2://user:pass@db:5432/convergence
    volumes:
      - ./superset_config.py:/app/superset_config.py
      - ./superset_home:/app/superset_home
    depends_on:
      - db

  superset-init:
    image: apache/superset:latest
    command: superset db upgrade && superset init && superset fab create-admin --username admin --firstname Admin --lastname User --email admin@convergence.io --password ${SUPERSET_ADMIN_PASSWORD}
    depends_on:
      - superset
```

### Import Dashboards

```bash
# Export dashboards as JSON
superset export-dashboards --path /app/dashboards/

# Import into production
superset import-dashboards --path /app/dashboards/
```

### Scheduled Reports

```python
# In Superset UI: Settings → Alerts & Reports

# Example: Daily convergence health email
{
    "name": "Daily Convergence Health",
    "cron": "0 8 * * *",
    "recipients": ["deal-team@convergence.io"],
    "dashboard_id": 1,
    "format": "pdf"
}
```
