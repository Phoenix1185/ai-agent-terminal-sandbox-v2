#!/bin/bash
set -e

echo "🚀 AI Agent Terminal & Sandbox v2.0 - Fly.io Deploy"
echo "===================================================="

if ! command -v flyctl &> /dev/null; then
    echo "❌ flyctl not found. Install from https://fly.io/docs/hands-on/install-flyctl/"
    exit 1
fi

APP_NAME="${FLY_APP_NAME:-ai-agent-terminal}"

echo "📦 Building Docker image..."
docker build -t $APP_NAME:latest .

echo "🔐 Setting secrets..."
if [ -z "$API_KEY" ]; then
    API_KEY=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)
    echo "Generated API Key: $API_KEY"
fi

flyctl secrets set API_KEY="$API_KEY" --app $APP_NAME || true
flyctl secrets set JWT_SECRET="$(openssl rand -base64 32)" --app $APP_NAME || true
flyctl secrets set DATABASE_URL="sqlite+aiosqlite:///data/app.db" --app $APP_NAME || true

echo "🚀 Deploying to Fly.io..."
flyctl deploy --app $APP_NAME --ha

echo "✅ Deployment complete!"
echo ""
echo "📊 App URL: https://$APP_NAME.fly.dev"
echo "🔑 API Key: $API_KEY"
echo "💾 Volume Path: /data (persistent across restarts)"
echo ""
echo "Next steps:"
echo "  1. Visit https://$APP_NAME.fly.dev for dashboard"
echo "  2. Use API with header: X-API-Key: $API_KEY"
echo "  3. Install tools: POST /api/v1/installer/install"
echo ""
echo "Scale commands:"
echo "  flyctl scale count 4 --app $APP_NAME"
echo "  flyctl scale vm performance-4x --app $APP_NAME"
