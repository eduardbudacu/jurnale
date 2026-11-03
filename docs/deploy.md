# Deploy to the server

Production runs on `192.168.2.23` from `/mnt/media/data/budisme.ro/jurnale`.
SSH access as `shv` uses a key that is already configured, so no password is
needed. For first-time setup (`.env`, superuser, pipeline) see
[DEPLOYMENT.md](../DEPLOYMENT.md).

## Steps

1. Connect to the server:

   ```bash
   ssh shv@192.168.2.23
   ```

2. Go to the project directory:

   ```bash
   cd /mnt/media/data/budisme.ro/jurnale
   ```

3. Pull the latest code:

   ```bash
   git pull
   ```

4. Rebuild and restart the containers:

   ```bash
   docker compose up -d --build db web
   ```

   The `web` container runs `migrate --fake-initial` on startup, so schema
   changes are applied automatically.

5. Check the deploy:

   ```bash
   docker compose ps
   docker compose logs --tail=50 web
   ```

   The dashboard is served on port 8081. If the MCP server is enabled, also
   run `docker compose --profile mcp up -d --build mcp` (see
   [DEPLOYMENT.md](../DEPLOYMENT.md)).

## One-liner

From your machine, all of the above in one command:

```bash
ssh shv@192.168.2.23 "cd /mnt/media/data/budisme.ro/jurnale && git pull && docker compose up -d --build db web && docker compose ps"
```
