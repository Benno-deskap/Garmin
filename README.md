# Garmin
Fetch Garmin data and use AI to give personal training advice

## What this does

This Docker Compose stack spins up three services that work together to fetch your Garmin fitness data and analyze it with AI:

- **n8n** — a self-hosted workflow automation tool (runs on port `5678`). This is the core engine that orchestrates all data fetching, processing, and AI analysis.
- **Browserless** — a headless Chrome instance (runs on port `3025`) used by n8n to perform browser-based tasks where needed.
- **Garmin API** — a lightweight Python/Flask server (runs on port `8085`) that connects to Garmin Connect using your credentials and exposes your health and activity data as a local API.

Your Garmin email and password are stored securely as Docker secrets and never exposed in the compose file directly.

---

## Step 1: Install Docker and Portainer on your NAS

Portainer is a web-based UI for managing Docker containers. It is required to create and manage the Docker stack in the next steps.

### On your NAS:
1. Install **Docker** via your NAS package manager or follow your NAS vendor's Docker installation guide
2. SSH into your NAS and run the following to install Portainer:
```bash
docker run -d \
  --name portainer \
  --restart unless-stopped \
  -p 9000:9000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /volume1/docker/portainer:/data \
  portainer/portainer-ce:latest
```

3. Open Portainer in your browser at `http://[your NAS IP]:9000`
4. Create an admin account on first launch
5. Select **Local** as the environment to manage your local Docker instance

---

## Step 2: Create the required directories on your NAS

Create the following folder structure. SSH into your NAS and run:
```bash
mkdir -p /volume1/docker/n8n
mkdir -p /volume1/docker/garmin-api/tokens
mkdir -p /volume1/docker/garmin-api/secrets
```

- `/volume1/docker/n8n` — stores all n8n data, workflows, and credentials
- `/volume1/docker/garmin-api/tokens` — stores the Garmin Connect session tokens after first login
- `/volume1/docker/garmin-api/secrets` — stores your Garmin login credentials as plain text files

---

## Step 3: Store your Garmin credentials

Create two plain text files in the secrets folder:
```bash
echo "your@email.com" > /volume1/docker/garmin-api/secrets/garmin_email.txt
echo "yourpassword" > /volume1/docker/garmin-api/secrets/garmin_password.txt
```

Each file should contain **only** the email or password, nothing else — no quotes, no newlines.

---

## Step 4: First-time Garmin login and MFA code

When the `garmin-api` container starts for the very first time, Garmin Connect will send a **one-time verification code to your email address** as part of their MFA (multi-factor authentication) process.

To complete the first login:

1. Start the stack in Portainer (see Step 6)
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

## Step 5: Generate your keys

### N8N_ENCRYPTION_KEY
This key is used by n8n to encrypt stored credentials. Generate a random 32+ character string. You can use any of these methods:

**Option A — OpenSSL (Linux/Mac/NAS SSH):**
```bash
openssl rand -hex 32
```

**Option B — Online:** use a password generator like [random.org](https://www.random.org/passwords/) and generate a 40+ character random string.

Copy the result and paste it as the value for `N8N_ENCRYPTION_KEY` in the compose file. **Save it somewhere safe** — if you lose it, your stored n8n credentials cannot be recovered.

### Browserless TOKEN
This token protects your browserless instance from unauthorized access. Generate it the same way as the encryption key — any random string works:
```bash
openssl rand -hex 24
```

Paste the result as the value for `TOKEN` in the compose file.

---

## Step 6: Deploy the stack in Portainer

1. In Portainer, go to **Stacks** → **Add Stack**
2. Give it a name (e.g. `garmin`)
3. Paste the YAML below into the **Web editor**
4. Replace `[enter your key here]` and `[enter your token here]` with the values you generated in Step 5
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
      - servarrnetwork
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
      - servarrnetwork
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
      - servarrnetwork
secrets:
  garmin_email:
    file: /volume1/docker/garmin-api/secrets/garmin_email.txt
  garmin_password:
    file: /volume1/docker/garmin-api/secrets/garmin_password.txt
networks:
  servarrnetwork:
    external: true
```
