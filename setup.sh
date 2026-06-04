#!/bin/bash
# Setup and validation script for Hacker News to Discord integration

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$HOME/.hacker-news-env"

echo "========================================="
echo "Hacker News to Discord - Setup Helper"
echo "========================================="
echo ""

# Check if venv exists
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "❌ Virtual environment not found."
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv "$SCRIPT_DIR/venv"
    echo "✓ Virtual environment created"
    echo ""
    echo "Installing dependencies..."
    "$SCRIPT_DIR/venv/bin/pip" install --no-user -r "$SCRIPT_DIR/requirements.txt" > /dev/null 2>&1
    echo "✓ Dependencies installed"
else
    echo "✓ Virtual environment found"
fi

echo ""
echo "========================================="
echo "Environment Configuration"
echo "========================================="
echo ""

# Check if env file exists
if [ -f "$ENV_FILE" ]; then
    echo "✓ Environment file found: $ENV_FILE"
    
    # Validate API key
    if grep -q "^GEMINI_API_KEY=" "$ENV_FILE"; then
        GEMINI_KEY=$(grep "^GEMINI_API_KEY=" "$ENV_FILE" | cut -d= -f2)
        if [ -z "$GEMINI_KEY" ] || [ "$GEMINI_KEY" = "your-gemini-api-key-here" ]; then
            echo "⚠️  GEMINI_API_KEY is not set"
        else
            echo "✓ GEMINI_API_KEY is set (${#GEMINI_KEY} chars)"
        fi
    else
        echo "❌ GEMINI_API_KEY not found in $ENV_FILE"
    fi
    
    # Validate Discord webhook
    if grep -q "^DISCORD_WEBHOOK_URL=" "$ENV_FILE"; then
        WEBHOOK=$(grep "^DISCORD_WEBHOOK_URL=" "$ENV_FILE" | cut -d= -f2)
        if [ -z "$WEBHOOK" ] || [[ "$WEBHOOK" == *"YOUR_WEBHOOK"* ]]; then
            echo "⚠️  DISCORD_WEBHOOK_URL is not set"
        else
            echo "✓ DISCORD_WEBHOOK_URL is set"
        fi
    else
        echo "❌ DISCORD_WEBHOOK_URL not found in $ENV_FILE"
    fi
else
    echo "❌ Environment file not found: $ENV_FILE"
    echo ""
    echo "To set up, run:"
    echo ""
    echo "  cat > $ENV_FILE << 'EOF'"
    echo "  GEMINI_API_KEY=your-api-key"
    echo "  DISCORD_WEBHOOK_URL=your-webhook-url"
    echo "  EOF"
    echo "  chmod 600 $ENV_FILE"
    echo ""
    echo "📚 Getting API Keys:"
    echo "  • Gemini API: https://aistudio.google.com/app/apikeys"
    echo "  • Discord Webhook: Discord Server > Settings > Integrations > Webhooks"
fi

echo ""
echo "========================================="
echo "Testing Python Dependencies"
echo "========================================="
echo ""

if "$SCRIPT_DIR/venv/bin/python3" -c "import requests, google.genai; print('✓ All imports successful')" 2>/dev/null; then
    echo "✓ Python dependencies are working"
else
    echo "❌ Python dependency import failed"
    exit 1
fi

echo ""
echo "========================================="
echo "Ready to run!"
echo "========================================="
echo ""
echo "To execute manually:"
echo "  source $ENV_FILE && $SCRIPT_DIR/run.sh"
echo ""
echo "To verify setup:"
echo "  $0"
echo ""
