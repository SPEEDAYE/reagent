# Deployment Cheat Sheet

> Full procedure: [../../DEPLOY_GUIDE.md](../../DEPLOY_GUIDE.md). This is a quick operator cheat sheet.

## Server Context

| Item | Value |
|------|-------|
| SSH host | `se.aiseclab.cn:10122` |
| SSH user | `carl` |
| Deploy path | `/home/carl/reagent/` |
| API bind | `0.0.0.0:8000` |
| Nginx (external) | `:9998` under location `/reagent/` |
| MongoDB | `localhost:27017` (no auth) |
| LLM | DeepSeek (`deepseek-chat`) |

## One-Click Deploy

```bash
./deploy.sh          # pack → upload → install → start
./deploy.sh pack     # local tarball only
./deploy.sh upload   # SCP tarball to remote
./deploy.sh remote   # install+start on remote
./deploy.sh verify   # remote status.sh
```

Environment overrides: `REMOTE_HOST`, `REMOTE_PORT`, `REMOTE_USER`, `REMOTE_PASS`, `REMOTE_DEPLOY_DIR`, `API_PORT`, `REMOTE_HEALTH_RETRIES`.

## Service Management (on server)

```bash
/home/carl/reagent/start.sh       # start (nohup uvicorn)
/home/carl/reagent/stop.sh        # stop (kill by PID file)
/home/carl/reagent/restart.sh     # stop + start
/home/carl/reagent/status.sh      # health check via curl
tail -f /home/carl/reagent/reagent-api.log
```

## Local SSH Tunnel

```bash
sshpass -p '...' ssh -p 10122 \
  -o ServerAliveInterval=30 \
  -L 8000:127.0.0.1:8000 \
  carl@se.aiseclab.cn -N -f

curl http://localhost:8000/health
```

## Env Template (`.env` in deploy dir)

```
OPENAI_KEY=sk-...
OPENAI_API_KEY=sk-...
OPENAI_MODEL=deepseek-chat
OPENAI_BASE_URL=https://api.deepseek.com/v1
MONGODB_URI=mongodb://localhost:27017
DB_NAME=reagent
```

See [../../util/llm_config.py](../../src/util/llm_config.py) for alternative provider env keys.

## Nginx (for SSE)

```nginx
location /reagent/ {
    rewrite ^/reagent/(.*) /$1 break;
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Connection '';
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 86400s;
}
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Connection refused` on localhost:8000 | Re-establish tunnel with `-o ServerAliveInterval=30` |
| `CHAPTER.__init__() missing SECTION` | `rm dataset/template-cache/*.pkl && ./restart.sh` |
| `Failed to connect to OpenAI API` | Set `OPENAI_BASE_URL` for non-OpenAI providers |
| `Survey file not found` | Verify `experiment/{pid}/` exists; `get_store_path()` must return relative path |
| SSE drops at 30 min | SSH: `-o ServerAliveInterval=30`; nginx: `proxy_read_timeout 86400s` |
| Mongo auth error | Disable auth: `sed -i 's/authorization: enabled/disabled/' /www/server/mongodb/config.conf` |
| New project shows 17 completed | Old bug (fixed) — should now isolate per `experiment/{pid}/` |
