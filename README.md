# Garmin Health & Training Advisor

Automatically fetch your Garmin fitness data every morning and receive a personal AI-powered training advice report in your inbox — built with n8n, Groq AI, and a self-hosted Garmin API.

## Workflow overview

<img width="1600" height="231" alt="image" src="https://github.com/user-attachments/assets/a82a9485-8829-49cd-a01b-7517e8d7ef1f" />


The workflow runs every morning at 08:00 and executes the following steps:

1. **Schedule Trigger** — fires every morning at 08:00
2. **Fetch all Garmin data** — retrieves your health and activity data from the local Garmin API (sleep, steps, heart rate, HRV, stress, weight, activities)
3. **Load Advice Memory** — loads previously generated advice for context
4. **Load 5K Training Schedule** — retrieves your current 5K running schedule
5. **Groq AI Analysis** — sends all data to Groq AI for personalised training advice
6. **Save Advice** — stores the generated advice for future reference
7. **Build HTML report** — generates a styled HTML email report with charts
8. **Send Email** — delivers the report to your inbox

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

| Field | Example (Gmail) |
|---|---|
| Host | `smtp.gmail.com` |
| Port | `465` (SSL) or `587` (TLS) |
| User | your sender email address |
| Password | your password or app password |
| SSL/TLS | enabled |

4. Click **Save**

**Gmail users — App Password required:**

Google requires an App Password instead of your regular password when using SMTP:

1. Go to [https://myaccount.google.com/security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** if not already active
3. Go to **App passwords**, choose **Mail**, click **Generate**
4. Use the 16-character code as your SMTP password in n8n

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
