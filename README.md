# 🤖 AI Agent Terminal & Sandbox v2.0

A comprehensive execution environment for AI agents with **Fly.io volumes**, **dynamic tool installation**, and **multi-machine API key consistency**.

## ✨ New in v2.0

- **💾 Fly.io Volumes**: Persistent storage at `/data` across restarts
- **📦 Dynamic Tool Installer**: Install any package (pip, npm, apt, cargo, gem, go, conda)
- **🔑 Volume-Backed API Keys**: Keys stored on volume, shared across all machines
- **💾 Session Persistence**: Terminal sessions survive restarts
- **📊 Volume Monitoring**: Track storage usage per machine
- **💾 Auto-Backup**: Create and restore volume backups

## 🚀 Quick Deploy

```bash
# 1. Set app name
export FLY_APP_NAME=your-app-name

# 2. Create volumes first (REQUIRED before deploy)
./scripts/setup-volumes.sh

# 3. Deploy
./scripts/deploy.sh

# 4. Scale to multiple machines
./scripts/setup-multi-machine.sh
```

## 📡 API Key Management

### Problem Solved
In multi-machine deployments, API keys set via `flyctl secrets` are inconsistent across machines. **v2.0 stores keys on the volume**, so all machines share the same key registry.

### Create New Key
```bash
curl -X POST https://your-app.fly.dev/api/v1/keys/create \
  -H "X-API-Key: your-master-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "Production Key", "permissions": ["*"]}'
```

### List Keys
```bash
curl https://your-app.fly.dev/api/v1/keys/list \
  -H "X-API-Key: your-master-key"
```

### Key Storage
- Master key from `API_KEY` env var (Fly.io secret)
- Additional keys stored in `/data/api_keys/keys.json`
- All machines read from the same volume file
- Backup auto-created at `/data/api_keys/keys.backup.json`

## 📦 Tool Installation

### Install Package
```bash
curl -X POST https://your-app.fly.dev/api/v1/installer/install \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"package": "requests", "manager": "pip"}'
```

### Install from GitHub
```bash
curl -X POST https://your-app.fly.dev/api/v1/installer/from-url \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/user/repo.git"}'
```

### Batch Install
```bash
curl -X POST https://your-app.fly.dev/api/v1/installer/install/batch \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '[{"package": "numpy"}, {"package": "pandas"}]'
```

## 💾 Volume Management

### Create Backup
```bash
curl -X POST https://your-app.fly.dev/api/v1/system/backup \
  -H "X-API-Key: your-key"
```

### List Backups
```bash
curl https://your-app.fly.dev/api/v1/system/backups \
  -H "X-API-Key: your-key"
```

### Restore Backup
```bash
curl -X POST "https://your-app.fly.dev/api/v1/system/restore?backup_file=backup_20240115_120000.tar.gz" \
  -H "X-API-Key: your-key"
```

## 🌍 Multi-Machine with Volumes

```bash
# Create 4 machines with 4 volumes (1:1 mapping)
flyctl scale count 2 --region iad
flyctl scale count 2 --region fra

# Each machine gets its own volume
# Data is NOT shared between volumes (by design)
# For shared data, use Redis or external database
```

## 🔒 Security

- API key auth on all endpoints
- Volume-based key storage for consistency
- Key hashing (never store plain keys)
- Permission-based access control
- Key expiration support
- Rate limiting per key

## 📁 Volume Structure

```
/data/
├── sandbox/        # Code execution files
├── sessions/       # Persisted terminal sessions
├── tools/          # Installed tools & packages
│   └── registry.json
├── logs/           # Application logs
├── backups/        # Volume backups
└── api_keys/       # API key storage
    ├── keys.json
    └── keys.backup.json
```

## 📝 License

MIT License
