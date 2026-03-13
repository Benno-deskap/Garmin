# Garmin
Fetch Garmin data and use AI to give personal training advice

## What this does

This Docker Compose stack spins up three services that work together to fetch your Garmin fitness data and analyze it with AI:

- **n8n** — a self-hosted workflow automation tool (runs on port `5678`). This is the core engine that orchestrates all data fetching, processing, and AI analysis.
- **Browserless** — a headless Chrome instance (runs on port `3025`) used by n8n to perform browser-based tasks where needed.
- **Garmin MCP** — a lightweight Python/Flask server (runs on port `8085`) that connects to Garmin Connect using your credentials and exposes your health and activity data as a local API.

Your Garmin email and password are stored securely as Docker secrets and never exposed in the compose file directly.

---

## Step 1: Install Docker and Portainer on your NAS

Portainer is a web-based UI for managing Docker containers. It is required to create and manage the Docker stack in the next steps.

### On Synology NAS:
1. Open **Package Center** and install **Container Manager** (this includes Docker)
2. SSH into your NAS and run the following to install Portainer:
```bash
