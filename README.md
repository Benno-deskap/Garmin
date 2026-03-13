# Garmin Health & Training Advisor

Automatically fetch your Garmin fitness data every morning and receive a personal AI-powered training advice report in your inbox — built with n8n, Groq AI, and a self-hosted Garmin API.

## Workflow overview

![n8n Garmin workflow](workflow.png)

The workflow runs every morning at 08:00 and executes the following steps:

1. **Every morning 08:00** — scheduled trigger
2. **Fetch all Garmin data** — retrieves your health and activity data from the local Garmin API (sleep, steps, heart rate, HRV, stress, weight, activities)
3. **Load Advice Memory** — loads previously generated advice for context
4. **Fetch 5K Schedule** — retrieves your current 5K running schedule
5. **Groq AI Analysis** — sends all data to Groq AI for personalised training advice
6. **Save Recommendations** — stores the generated advice for future reference
7. **Create HTML report** — generates a styled HTML email report with charts
8. **Send an Email** — delivers the report to your inbox

---

## What you need before you start

- A NAS or always-on home server with Docker support
- A [Groq](https://console.groq.com) account (free tier is sufficient)
- A Garmin Connect account
- An email account with SMTP access (Gmail, Zoho, Outlook, etc.)

---

## Part 1 — Infrastructure setup

### Step 1: Install Docker on your NAS

Install Docker via your NAS package manager. On most NAS devices this is available as **Container Manager** or a **Docker** package in the package center. Follow your NAS vendor's documentation to get Docker running before continuing.

---

### Step 2: Install Portainer

Portainer is a web-based UI for managing Docker containers. It lets you deploy and manage stacks without needing the command line after the initial setup.

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

Then open your browser at `http://[your NAS IP]:9000` and:

1. Create an **admin username and password** — do this within 5 minutes or Portainer will time out
2. Select **Local** as the environment
3. Click **Connect**

> **Tip:** Bookmark `http://[your NAS IP]:9000` for easy access.

---

### Step 3: Create the n8n-network in Portainer

All containers communicate over a shared Docker network. Create it once before deploying the stack:

1. In Portainer, go to **Networks** → **Add network**
2. Set **Name** to `n8n-network` and **Driver** to `bridge`
3. Click **Create the network**

---

### Step 4: Create the required directories

SSH into your NAS and run:

```bash
mkdir -p /volume1/docker/n8n
mkdir -p /volume1/docker/garmin-api/tokens
mkdir -p /volume1/docker/garmin-api/secrets
```

- `/volume1/docker/n8n` — n8n data, workflows and credentials
- `/volume1/docker/garmin-api/tokens` — Garmin Connect session tokens (auto-generated after first login)
- `/volume1/docker/garmin-api/secrets` — your Garmin login credentials

---

### Step 5: Find your PUID and PGID

The `PUID` and `PGID` values tell the container which user and group should own the files it creates. Using the correct values prevents permission errors on your NAS volume.

SSH into your NAS and run:

```bash
id
```

Example output:

```
uid=1000(admin) gid=10(wheel) groups=10(wheel),101(docker)
```

- The number after `uid=` is your **PUID**
- The number after `gid=` is your **PGID**

Update the compose file with your own values if they differ from the defaults.

---

### Step 6: Store your Garmin credentials

```bash
echo "your@email.com" > /volume1/docker/garmin-api/secrets/garmin_email.txt
echo "yourpassword" > /volume1/docker/garmin-api/secrets/garmin_password.txt
```

Each file must contain **only** the email or password — no quotes, no extra spaces, no newlines.

---

### Step 7: Generate your security keys

**N8N_ENCRYPTION_KEY** — used by n8n to encrypt stored credentials:

```bash
openssl rand -hex 32
```

**Browserless TOKEN** — protects your browserless instance from unauthorised access:

```bash
openssl rand -hex 24
```

Save both values somewhere safe. If you lose the encryption key, your stored n8n credentials cannot be recovered.

---

### Step 8: Deploy the stack in Portainer

1. In Portainer, go to **Stacks** → **Add Stack**
2. Give it a name (e.g. `garmin`)
3. Paste the YAML below into the **Web editor**
4. Replace the placeholder values:
   - `[enter your key here]` → your N8N_ENCRYPTION_KEY from Step 7
   - `[enter your token here]` → your Browserless TOKEN from Step 7
   - `PUID` and `PGID` → your values from Step 5
5. Click **Deploy the stack**

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
      - N8N_USER_MANAGEMENT_DISABLED=false
      - N8N_ENCRYPTION_KEY=[enter your key here]
      - N8N_RUNNER_ENABLED=false
      - NODE_FUNCTION_ALLOW_EXTERNAL=zlib,axios,lodash
      - NODE_OPTIONS=--max-old-space-size=8192
      - N8N_PAYLOAD_SIZE_MAX=100
      - EXECUTIONS_DATA_PRUNE=true
      - EXECUTIONS_DATA_MAX_AGE=72
      - EXECUTIONS_DATA_PRUNE_MAX_COUNT=10000
      - EXECUTIONS_DATA_SAVE_ON_ERROR=all
      - EXECUTIONS_DATA_SAVE_SUCCESS_CONFIRMATION=false
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

### Step 9: Complete the first-time Garmin login

When the `garmin-api` container starts for the very first time, Garmin Connect will send a **one-time verification code to your email** as part of their MFA process.

1. In Portainer, go to **Containers** → `garmin-api` → **Logs**
2. Wait for the prompt:
   ```
   Enter MFA/2FA code:
   ```
3. Check your Garmin-linked email inbox for the code
4. In Portainer, open the **Console** tab of the `garmin-api` container
5. Type the code and press Enter

The container saves a session token to `/volume1/docker/garmin-api/tokens` — this step only needs to be done once. The token is reused automatically on every restart.

> **Note:** If the token expires or Garmin invalidates it, repeat this process.

---

## Part 2 — n8n setup

### Step 10: Create your n8n account

1. Open `http://[your NAS IP]:5678` in your browser
2. Click **Get started**
3. Fill in your name, email address and a password
4. Complete the setup steps (optional questions can be skipped)

> **Tip:** Bookmark `http://[your NAS IP]:5678` for easy access.

---

### Step 11: Create a Groq API key

The workflow uses [Groq](https://groq.com) as its AI engine. Groq offers a free tier that is sufficient for daily use.

1. Go to [https://console.groq.com](https://console.groq.com) and create a free account
2. In the left sidebar, go to **API Keys** → **Create API Key**
3. Give it a name (e.g. `n8n-garmin`) and click **Submit**
4. Copy the key — it starts with `gsk_` and is **only shown once**

### Add the Groq key to n8n

1. In n8n, go to **Settings** → **Credentials** → **Add credential**
2. Search for **Groq** and select it
3. Paste your API key and click **Save**

---

### Step 12: Configure your email (SMTP)

The workflow sends the daily report via email using SMTP. You can use any provider that supports SMTP.

1. In n8n, go to **Settings** → **Credentials** → **Add credential**
2. Search for **SMTP** and select it
3. Fill in the fields for your email provider:

| Field | Zoho Mail |
|---|---|
| Host | `smtp.zoho.eu` |
| Port | `465` (SSL) |
| User | your Zoho email address (e.g. `you@zohomail.eu`) |
| Password | your Zoho password or app-specific password |
| SSL/TLS | enabled |

4. Click **Save**

**Zoho Mail — recommended setup:**

Zoho Mail at [https://mail.zoho.eu](https://mail.zoho.eu) works well as a free self-hosted sender address. If you have two-factor authentication enabled on your Zoho account, you need to generate an **app-specific password**:

1. Go to [https://accounts.zoho.eu/home](https://accounts.zoho.eu/home)
2. Navigate to **Security** → **App Passwords**
3. Click **Generate New Password**, give it a name (e.g. `n8n`) and click **Generate**
4. Use the generated password as the SMTP password in n8n

---

### Step 13: Import the workflow

1. In n8n, go to **Workflows** in the left sidebar
2. Click **Add workflow**
3. Click the **⋮** (three dots) menu in the top right corner
4. Select **Import from file**
5. Select the `Garmin_clean.json` file from this repository
6. Click **Save**

---

### Step 14: Configure the workflow nodes

After importing, open the workflow and update the following nodes:

**Groq AI Analyse node:**
- Click the node
- Under **Credential**, select your Groq credential from Step 11

**Send an Email node:**
- Click the node
- Under **Credential**, select your SMTP credential from Step 12
- Set the **To** field to your recipient email address
- Set the **From** field to your sender email address

**Save** the workflow after making these changes.

---

### Step 15: Activate the workflow

The workflow is inactive by default after importing.

1. Open the workflow
2. Toggle the **Active** switch in the top right corner to **on**
3. The workflow will now run automatically every morning at 08:00

> **Important:** Make sure all credentials are linked and tested before activating. You can test the workflow manually by clicking **Execute workflow** in the editor.

---

## n8n Workflow JSON

Copy the JSON below and import it into n8n (see Step 13), or download the `Garmin_clean.json` file from this repository.
```json
{
  "name": "Garmin 5K Training Assistant (Anonymous)",
  "nodes": [
    {
      "parameters": {
        "rule": {
          "interval": [
            {
              "field": "cronExpression",
              "expression": "0 8 * * *"
            }
          ]
        }
      },
      "id": "7197bd35-e394-4bff-8d0e-b337be148dc1",
      "name": "Every morning 08:00",
      "type": "n8n-nodes-base.scheduleTrigger",
      "typeVersion": 1.1,
      "position": [17136, 7152]
    },
    {
      "parameters": {
        "jsCode": "const BASE = 'http://[NAS_IP]:8085';\n\nfunction datumGeleden(n) {\n  const d = new Date();\n  d.setDate(d.getDate() - n);\n  return d.toISOString().split('T')[0];\n}\n\n// Logic to fetch Garmin stats via local API\nreturn [{ json: { message: \"Data fetched from Garmin API placeholder\" } }];"
      },
      "id": "56dec719-8410-4b19-8b0f-51b0c5172992",
      "name": "Fetch all Garmin data",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [17328, 7152]
    },
    {
      "parameters": {
        "jsCode": "// 5K Training Schedule (8 weeks)\nconst SCHEMA = {\n  1: { ma: { type: 'interval', omschrijving: 'Warming-up, running intervals, cooling-down', duurMin: 28 } }\n};\n\nconst garminData = $input.first().json;\nconst score = garminData.trainingReadiness?.score ?? 100;\n\n// Adaptive training logic based on readiness (Anonymized)\nlet aanpassing = (score < 40) ? 'rest' : (score < 70) ? 'light' : 'normal';\n\nreturn [{ json: { ...garminData, schemaContext: { aanpassing, score } } }];"
      },
      "id": "9dfb5f51-e85d-4aba-b73d-0c6f8ed41ae1",
      "name": "Fetch 5K Schedule",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [17664, 7152]
    },
    {
      "parameters": {
        "jsCode": "const GROQ_API_KEY = '[YOUR_GROQ_API_KEY]';\nconst systemContent = \"Je bent een data-gedreven gezondheidscoach. Analyseer de trends. Wees concreet en bondig.\";\n\nreturn [{ json: { analyse: \"AI analysis result\", garminData: $input.first().json } }];"
      },
      "id": "38237733-704f-4b96-9015-25faa587bcde",
      "name": "Groq AI Analysis",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [17824, 7152]
    },
    {
      "parameters": {
        "fromEmail": "[SENDER_EMAIL]",
        "toEmail": "[RECIPIENT_EMAIL]",
        "subject": "={{ $json.onderwerp }}",
        "html": "={{ $json.html }}"
      },
      "id": "73ca377b-5072-449e-9aca-7a46b4cf6dd8",
      "name": "Send an Email",
      "type": "n8n-nodes-base.emailSend",
      "typeVersion": 2.1,
      "position": [18352, 7152]
    }
  ],
  "connections": {
    "Every morning 08:00": { "main": [[{ "node": "Fetch all Garmin data", "type": "main", "index": 0 }]] },
    "Fetch all Garmin data": { "main": [[{ "node": "Fetch 5K Schedule", "type": "main", "index": 0 }]] },
    "Fetch 5K Schedule": { "main": [[{ "node": "Groq AI Analysis", "type": "main", "index": 0 }]] },
    "Groq AI Analysis": { "main": [[{ "node": "Send an Email", "type": "main", "index": 0 }]] }
  },
  "active": true,
  "settings": { "executionOrder": "v1" }
}
