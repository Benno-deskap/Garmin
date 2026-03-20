# 🏃 Garmin Health & Training Advisor

> Automatically fetch your Garmin fitness data every morning and receive a personalised AI-powered training advice report in your inbox.

![n8n](https://img.shields.io/badge/n8n-workflow-EA4B71?logo=n8n&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-AI-F55036?logo=groq&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-self--hosted-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

---

## 📋 Table of Contents

- [What it does](#-what-it-does)
- [Daily email report](#-daily-email-report)
- [Requirements](#-requirements)
- [Part 1 — Infrastructure setup](#part-1--infrastructure-setup)
- [Part 2 — n8n setup](#part-2--n8n-setup)
- [API endpoints](#-api-endpoints)
- [Changelog](#-changelog)

---

## ✨ What it does

Every morning at **08:00** this workflow automatically:

1. Fetches all your Garmin health and activity data via a self-hosted Python API
2. Loads previously generated advice for context
3. Sends everything to **Groq AI** for personalised training analysis
4. Saves the recommendations for continuity
5. Generates a styled **HTML email report** with charts
6. Delivers the report straight to your inbox

![Workflow overview](https://github.com/user-attachments/assets/72a8f9b7-c098-4529-8ee8-40c3da8d619c)

---

## 📧 Daily email report

Each morning you receive a full personal health and training overview:

| Section | Contents |
|---|---|
| **Header** | One-line summary — sleep trend, step streak, resting heart rate, VO2max status |
| **Stats dashboard** | Weekly averages: sleep, steps, Body Battery, HRV, stress, VO2max, intensity minutes, weight, Training Readiness |
| **Training advice** | Adjusted based on Training Readiness and ACWR — includes planned Garmin workouts with warmup → intervals → cooldown |
| **AI health analysis** | Full written analysis by Groq (see details below) |

<details>
<summary><strong>Full AI analysis breakdown (16 sections)</strong></summary>

1. Weekly overview and trends
2. Sleep analysis — best/worst night, deep sleep, REM and SpO2 patterns
3. Heart rate and HRV trends
4. Training Readiness and load balance — ACWR, aerobic low/high breakdown
5. Fitness age and VO2max estimate — improvement potential and component breakdown
6. Race predictions — 5K, 10K, half marathon, marathon
7. Planned Garmin workouts — with advice to execute, adjust or skip
8. Heart rate zone distribution
9. Movement and step analysis — sedentary time vs WHO goal
10. Body Battery and stress trends
11. Weight trend — current weight, 30-day delta, distance to goal, BMI
12. Top correlations between metrics — with exact dates and values
13. Top 5 sleep recommendations
14. Top 5 movement recommendations
15. Goals for next week
16. Concrete actions for today

</details>

---

## 🛠 Requirements

- A NAS or always-on home server with **Docker** support
- A [Groq](https://console.groq.com) account — free tier is sufficient
- A **Garmin Connect** account with workouts planned in the app or via Garmin Coach
- An email account with **SMTP** access (Gmail, Zoho, Outlook, etc.)

---

## Part 1 — Infrastructure setup

### Step 1: Install Docker on your NAS

Install Docker via your NAS package manager. On most NAS devices this is available as **Container Manager** in the package center. Follow your NAS vendor's documentation before continuing.

---

### Step 2: Install Portainer

Portainer is a web-based UI for managing Docker containers — no command line needed after the initial setup.

SSH into your NAS and run:

```bash
docker run -d \
  --name portainer \
  --restart unless-stopped \
  -p 9000:9000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /volume1/docker/portainer:/data \
  portainer/portainer-ce:latest
```

Open `http://[your NAS IP]:9000`, create an admin account (within 5 minutes), select **Local** and click **Connect**.

---

### Step 3: Create the Docker network

In Portainer: **Networks → Add network → Name:** `n8n-network` **→ Driver:** `bridge` → **Create**.

---

### Step 4: Create the required directories

```bash
mkdir -p /volume1/docker/n8n
mkdir -p /volume1/docker/garmin-api/tokens
mkdir -p /volume1/docker/garmin-api/secrets
```

---

### Step 5: Find your PUID and PGID

```bash
id
# uid=1000(admin) gid=10(wheel) ...
```

Note your `uid` (PUID) and `gid` (PGID) — you'll need them in the compose file.

---

### Step 6: Store your Garmin credentials

```bash
echo "your@email.com" > /volume1/docker/garmin-api/secrets/garmin_email.txt
echo "yourpassword"   > /volume1/docker/garmin-api/secrets/garmin_password.txt
```

> ⚠️ Each file must contain **only** the value — no quotes, no spaces, no newlines.

---

### Step 7: Generate your security keys

```bash
# N8N encryption key
openssl rand -hex 32

# Browserless token
openssl rand -hex 24
```

> 🔑 Save both values. If you lose the N8N encryption key, stored credentials cannot be recovered.

---

### Step 8: Deploy the stack in Portainer

Go to **Stacks → Add Stack**, paste the YAML below and replace the placeholders.

```yaml
version: "3.9"
services:
  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    restart: unless-stopped
    ports:
      - "5678:5678"
    environment:
      - PUID=1000
      - PGID=10
      - TZ=Europe/Amsterdam
      - GENERIC_TIMEZONE=Europe/Amsterdam
      - NODE_ENV=production
      - N8N_SECURE_COOKIE=false
      - N8N_ENCRYPTION_KEY=[enter your key here]
      - NODE_FUNCTION_ALLOW_EXTERNAL=zlib,axios,lodash
      - NODE_OPTIONS=--max-old-space-size=8192
      - N8N_PAYLOAD_SIZE_MAX=100
      - EXECUTIONS_DATA_PRUNE=true
      - EXECUTIONS_DATA_MAX_AGE=72
      - EXECUTIONS_DATA_PRUNE_MAX_COUNT=10000
      - EXECUTIONS_DATA_SAVE_ON_ERROR=all
    volumes:
      - /volume1/docker/n8n:/home/node/.n8n
    networks:
      - n8n-network
    deploy:
      resources:
        limits:
          memory: 12G
        reservations:
          memory: 2G

  browserless:
    image: browserless/chrome:latest
    container_name: browserless
    restart: unless-stopped
    ports:
      - "3025:3000"
    environment:
      - MAX_CONCURRENT_SESSIONS=2
      - TOKEN=[enter your token here]
    shm_size: 1gb
    networks:
      - n8n-network

  garmin-api:
    image: python:3.12-slim
    container_name: garmin-api
    restart: unless-stopped
    working_dir: /app
    entrypoint: bash -c "pip install --no-cache-dir garminconnect flask && python /app/server.py"
    ports:
      - "8085:8080"
    volumes:
      - /volume1/docker/garmin-api/server.py:/app/server.py
      - /volume1/docker/garmin-api/tokens:/root/.garminconnect
    secrets:
      - garmin_email
      - garmin_password
    networks:
      - n8n-network

secrets:
  garmin_email:
    file: /volume1/docker/garmin-api/secrets/garmin_email.txt
  garmin_password:
    file: /volume1/docker/garmin-api/secrets/garmin_password.txt

networks:
  n8n-network:
    external: true
```

---

### Step 9: Deploy the Garmin API server script

Download [`server.py`](./server.py) from this repository and copy it to your NAS:

```bash
cp server.py /volume1/docker/garmin-api/server.py
```

The script is a Flask web server that bridges Garmin Connect and your n8n workflow. n8n reaches it at `http://garmin-api:8080` over the internal Docker network (mapped to port `8085` on your NAS).

---

### Step 10: Complete the first-time Garmin login

On first start, Garmin will send a **one-time MFA code** to your email.

1. In Portainer → **Containers → garmin-api → Logs** — wait for `Enter MFA/2FA code:`
2. Check your inbox for the code
3. Open the **Console** tab, type the code and press Enter

The session token is saved to `/volume1/docker/garmin-api/tokens` — this only needs to be done once.

---

## Part 2 — n8n setup

### Step 11: Create your n8n account

Open `http://[your NAS IP]:5678`, click **Get started** and complete the setup.

---

### Step 12: Add your Groq API key

1. Go to [https://console.groq.com](https://console.groq.com) → **API Keys → Create API Key**
2. Copy the key (starts with `gsk_` — shown **once only**)
3. In n8n: **Settings → Credentials → Add credential → Groq** → paste and save

---

### Step 13: Configure SMTP email

In n8n: **Settings → Credentials → Add credential → SMTP**

| Field | Zoho Mail example |
|---|---|
| Host | `smtp.zoho.eu` |
| Port | `465` (SSL) |
| User | `you@zohomail.eu` |
| Password | your password or app-specific password |
| SSL/TLS | enabled |

> **Zoho Mail tip:** If you use 2FA, generate an app password at [accounts.zoho.eu](https://accounts.zoho.eu) → **Security → App Passwords**.

---

### Step 14: Import the workflow

1. In n8n: **Workflows → Add workflow → ⋮ → Import from file**
2. Select `Garmin_clean.json` from this repository
3. Click **Save**

---

### Step 15: Configure the workflow nodes

After importing, update these three nodes:

| Node | What to update |
|---|---|
| **Groq AI Analysis** | Select your Groq credential |
| **Send an Email** | Select SMTP credential, set To/From addresses |
| **Fetch all Garmin data** | Replace `[your NAS IP]` with your actual NAS IP |

---

### Step 16: Activate the workflow

Toggle the **Active** switch in the top-right corner. The workflow will now run every morning at 08:00.

> 💡 Test first by clicking **Execute workflow** manually before activating.

---

## 🔌 API endpoints

The Garmin API server exposes the following endpoints:

| Endpoint | Data |
|---|---|
| `/health` | Connection status |
| `/slaap` | Sleep duration, stages, score |
| `/stappen` | Daily step count and goal |
| `/hartslag` | Resting heart rate and daily averages |
| `/hrv` | Heart Rate Variability |
| `/stress` | Stress level throughout the day |
| `/stats` | General daily stats summary |
| `/gewicht` | Weight and body composition (daily + 30-day) |
| `/activiteiten` | Recent activities |
| `/training-readiness` | Training Readiness score and feedback |
| `/training-status` | Training Status, ACWR, VO2max |
| `/vo2max` | VO2max and fitness age |
| `/race-predictions` | Predicted times: 5K, 10K, HM, Marathon |
| `/hartslagzones` | Heart rate zone distribution |
| `/activiteit-zones` | HR zones for a specific activity |
| `/fitnessleeftijd` | Fitness age |
| `/persoonlijke-records` | Personal records per distance |
| `/workouts` | Planned workouts from Garmin Connect |
| `/workout-detail` | Step-by-step breakdown of a single workout |

---

## 📝 Changelog

See [Change-log](./Change-log) for the full version history.

---

## ⭐ Found this useful?

If this project helps your training, consider giving it a star on GitHub — it helps others find it too.
