# Garmin
Fetch Garmin data and use AI to give personal training advice

## What this does

This Docker Compose stack spins up three services that work together to fetch your Garmin fitness data and analyze it with AI:

- **n8n** — a self-hosted workflow automation tool (runs on port `5678`). This is the core engine that orchestrates all data fetching, processing, and AI analysis.
- **Browserless** — a headless Chrome instance (runs on port `3025`) used by n8n to perform browser-based tasks where needed.
- **Garmin API** — a lightweight Python/Flask server (runs on port `8085`) that connects to Garmin Connect using your credentials and exposes your health and activity data as a local API.

Your Garmin email and password are stored securely as Docker secrets and never exposed in the compose file directly.

## Workflow overview

![n8n Garmin workflow](Scherm_afbeelding_2026-03-13_om_18_45_09.png)

The workflow runs every morning at 08:00 and executes the following steps:
1. **Elke ochtend 08:00** — scheduled trigger
2. **Haal alle Garmin data op** — fetches all health and activity data from the Garmin API
3. **Laad Advies Geheugen** — loads previous advice from memory
4. **Haal 5K Schema Op** — retrieves your 5K training schedule
5. **Groq AI Analyse** — sends all data to Groq AI for analysis and personal training advice
6. **Sla Adviezen Op** — saves the generated advice to memory
7. **Maak HTML rapport** — builds a styled HTML report
8. **Send an Email** — delivers the report to your inbox

---

## Step 1: Install Portainer on your NAS

Portainer is a web-based UI for managing Docker containers. It runs as a Docker container itself and gives you a visual interface to deploy and manage stacks without needing the command line after initial setup.

### Prerequisites
- Docker must already be running on your NAS. Install it via your NAS package manager (e.g. Container Manager, Docker package) before continuing.

### Install Portainer via SSH

SSH into your NAS and run this single command:
```bash
docker run -d \
  --name portainer \
  --restart unless-stopped \
  -p 9000:9000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /volume1/docker/portainer:/data \
  portainer/portainer-ce:latest
```

This will:
- Pull the latest Portainer Community Edition image
- Start it as a background container that survives reboots
- Expose the web UI on port `9000`
- Mount the Docker socket so Portainer can manage your containers
- Store Portainer's own data in `/volume1/docker/portainer`

### First-time setup

1. Open your browser and go to `http://[your NAS IP]:9000`
2. You will be prompted to create an **admin username and password** — do this within 5 minutes or Portainer will time out and you'll need to restart the container
3. On the next screen, select **Local** as the environment
4. Click **Connect** — you now have full Docker management via the Portainer web UI

> **Tip:** Bookmark `http://[your NAS IP]:9000` for easy access.

---

## Step 2: Create the n8n-network in Portainer

All three containers communicate with each other over a shared Docker network called `n8n-network`. You need to create this network once before deploying the stack.

1. In Portainer, go to **Networks** → **Add network**
2. Fill in the following:
   - **Name:** `n8n-network`
   - **Driver:** `bridge`
   - Leave all other settings as default
3. Click **Create the network**

---

## Step 3: Create the required directories on your NAS

SSH into your NAS and run:
```bash
mkdir -p /volume1/docker/n8n
mkdir -p /volume1/docker/garmin-api/tokens
mkdir -p /volume1/docker/garmin-api/secrets
```

- `/volume1/docker/n8n` — stores all n8n data, workflows, and credentials
- `/volume1/docker/garmin-api/tokens` — stores the Garmin Connect session tokens after first login
- `/volume1/docker/garmin-api/secrets` — stores your Garmin login credentials as plain text files

### Find your PUID and PGID

The `PUID` and `PGID` values tell the container which user and group should own the files it creates. Using the correct values prevents permission errors on your NAS volume.

SSH into your NAS and run:
```bash
id
```

You will see output like:
```
uid=1000(admin) gid=10(wheel) groups=10(wheel),101(docker)
```

- The number after `uid=` is your **PUID** → use this as the value for `PUID`
- The number after `gid=` is your **PGID** → use this as the value for `PGID`

In the example above: `PUID=1000` and `PGID=10`. Update the compose file with your own values if they differ.

---

## Step 4: Store your Garmin credentials

Create two plain text files in the secrets folder:
```bash
echo "your@email.com" > /volume1/docker/garmin-api/secrets/garmin_email.txt
echo "yourpassword" > /volume1/docker/garmin-api/secrets/garmin_password.txt
```

Each file should contain **only** the email or password, nothing else — no quotes, no newlines.

---

## Step 5: First-time Garmin login and MFA code

When the `garmin-api` container starts for the very first time, Garmin Connect will send a **one-time verification code to your email address** as part of their MFA (multi-factor authentication) process.

To complete the first login:

1. Start the stack in Portainer (see Step 7)
2. Open the logs of the `garmin-api` container in Portainer → **Containers** → `garmin-api` → **Logs**
3. Watch for a prompt like:
```
   Enter MFA/2FA code: 
```
4. Check your Garmin-linked email inbox for the verification code
5. In Portainer, open the container's **Console** (attach to the running container) and type the code, then press Enter
6. The container will save a session token to `/volume1/docker/garmin-api/tokens` — **this only needs to be done once**. After that, the token is reused automatically on restart.

> **Note:** If the token expires or Garmin invalidates it, you may need to repeat this process.

---

## Step 6: Generate your keys

### N8N_ENCRYPTION_KEY
This key is used by n8n to encrypt stored credentials. Generate a random 32+ character string. You can use any of these methods:

**Option A — OpenSSL (via SSH):**
```bash
openssl rand -hex 32
```

**Option B — Online:** use a password generator like [random.org](https://www.random.org/passwords/) and generate a 40+ character random string.

Copy the result and paste it as the value for `N8N_ENCRYPTION_KEY` in the compose file. **Save it somewhere safe** — if you lose it, your stored n8n credentials cannot be recovered.

### Browserless TOKEN
This token protects your browserless instance from unauthorized access. Generate it the same way:
```bash
openssl rand -hex 24
```

Paste the result as the value for `TOKEN` in the compose file.

---

## Step 7: Deploy the stack in Portainer

1. In Portainer, go to **Stacks** → **Add Stack**
2. Give it a name (e.g. `garmin`)
3. Paste the YAML below into the **Web editor**
4. Replace `[enter your key here]` and `[enter your token here]` with the values you generated in Step 6
5. Update `PUID` and `PGID` with the values you found in Step 3
6. Click **Deploy the stack**
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

## Step 8: First-time login in n8n and create your account

1. Open your browser and go to `http://[your NAS IP]:5678`
2. You will be greeted by the n8n setup screen — click **Get started**
3. Fill in the following to create your admin account:
   - **First name** and **Last name**
   - **Email address** — this will be your login username
   - **Password**
4. Click **Next** and follow the remaining setup steps (you can skip optional questions)
5. You are now logged in to your n8n instance

> **Tip:** Bookmark `http://[your NAS IP]:5678` for easy access.

---

## Step 9: Import the Garmin workflow

### Option A — Import from a JSON file

1. In n8n, go to the **Workflows** overview (left sidebar)
2. Click **Add workflow** → in the top right corner click the **⋮** (three dots) menu → **Import from file**
3. Select the downloaded `.json` workflow file
4. The workflow will open in the editor — click **Save** in the top right corner

### Option B — Import from clipboard

1. Open the `.json` file in a text editor and copy all the contents
2. In n8n, go to **Workflows** → **Add workflow**
3. Click the **⋮** menu in the top right → **Import from URL / clipboard**
4. Paste the JSON and confirm
5. Click **Save**

### Activate the workflow

After importing, the workflow is inactive by default. To enable the scheduled trigger:

1. Open the workflow
2. Toggle the **Active** switch in the top right corner from off to on
3. The workflow will now run automatically every morning at 08:00

> **Note:** Make sure all credentials (email, Groq API key) are configured in the workflow nodes before activating.
