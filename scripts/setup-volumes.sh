#!/bin/bash
set -e

APP_NAME="${FLY_APP_NAME:-ai-agent-terminal}"

echo "💾 Setting up Fly.io Volumes for AI Agent Terminal"
echo "==================================================="

# Create volumes (1 per machine, minimum 2 for redundancy)
echo "📦 Creating volumes..."

# Volume in primary region (iad)
flyctl volumes create agent_data \
    --region iad \
    --size 10 \
    --app $APP_NAME \
    --yes || echo "Volume may already exist"

# Second volume in primary region for redundancy
flyctl volumes create agent_data \
    --region iad \
    --size 10 \
    --app $APP_NAME \
    --yes || echo "Volume may already exist"

# Volume in secondary region (fra)
flyctl volumes create agent_data \
    --region fra \
    --size 10 \
    --app $APP_NAME \
    --yes || echo "Volume may already exist"

# Fourth volume in secondary region
flyctl volumes create agent_data \
    --region fra \
    --size 10 \
    --app $APP_NAME \
    --yes || echo "Volume may already exist"

echo "✅ Volumes created!"
echo ""
echo "📊 Volume status:"
flyctl volumes list --app $APP_NAME

echo ""
echo "🔧 Now deploy with:"
echo "  ./scripts/deploy.sh"
