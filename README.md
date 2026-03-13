# Garmin
Fetch Garmin data and use AI to give personal training advice

## Step 1: Setup Docker

## Step 2: Make a new Docker instance using the below YAML in your Stack
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
  garmin-mcp:
    image: python:3.12-slim
    container_name: garmin-mcp
    restart: unless-stopped
    working_dir: /app
    entrypoint: bash -c "pip install --no-cache-dir garminconnect flask && python /app/server.py"
    ports:
      - "8085:8080"
    volumes:
      - /volume1/docker/garmin-mcp/server.py:/app/server.py
      - /volume1/docker/garmin-mcp/tokens:/root/.garminconnect
    secrets:
      - garmin_email
      - garmin_password
    networks:
      - servarrnetwork
secrets:
  garmin_email:
    file: /volume1/docker/garmin-mcp/secrets/garmin_email.txt
  garmin_password:
    file: /volume1/docker/garmin-mcp/secrets/garmin_password.txt
networks:
  servarrnetwork:
    external: true
```
