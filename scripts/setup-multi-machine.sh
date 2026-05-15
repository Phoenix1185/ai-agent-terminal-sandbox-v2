#!/bin/bash
set -e

APP_NAME="${FLY_APP_NAME:-ai-agent-terminal}"

echo "🔧 Multi-Machine Setup with Volumes"
echo "===================================="

# Create app if not exists
flyctl apps create $APP_NAME --machines || true

# Set regions
flyctl regions set iad fra --app $APP_NAME

# Create volumes first
./scripts/setup-volumes.sh

# Scale to 4 machines (2 per region, each with its own volume)
echo "📈 Scaling to 4 machines with volumes..."
flyctl scale count 2 --region iad --app $APP_NAME
flyctl scale count 2 --region fra --app $APP_NAME

# Set VM size
echo "💪 Setting VM size to performance-2x..."
flyctl scale vm performance-2x --app $APP_NAME

echo "✅ Multi-machine setup complete!"
echo ""
echo "Current status:"
flyctl status --app $APP_NAME

echo ""
echo "Volume list:"
flyctl volumes list --app $APP_NAME
