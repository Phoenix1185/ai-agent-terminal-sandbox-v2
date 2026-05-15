#!/bin/bash
set -e

APP_NAME="${FLY_APP_NAME:-ai-agent-terminal}"

echo "💾 Creating Volume Backup"
echo "========================="

# Create on-demand snapshot
echo "📸 Creating snapshot..."
flyctl volumes snapshot create --app $APP_NAME

echo "✅ Backup initiated!"
echo ""
echo "View snapshots:"
echo "  flyctl volumes list --app $APP_NAME"
echo ""
echo "Restore from snapshot:"
echo "  flyctl volumes create --snapshot-id <id> --app $APP_NAME"
