#!/bin/bash
# Hacker News to Discord - Execution Script with Git automation

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/main.py"
VENV_PYTHON="$SCRIPT_DIR/venv/bin/python3"
ARCHIVE_DIR="$SCRIPT_DIR/Archive"

echo "========================================="
echo "Starting Hacker News to Discord script"
echo "Time: $(date)"
echo "========================================="

# Check if Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "✗ Python script not found: $PYTHON_SCRIPT"
    exit 1
fi

# Check if venv exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "✗ Virtual environment not found. Please run: python3 -m venv venv && venv/bin/pip install -r requirements.txt"
    exit 1
fi

# Check if GEMINI_API_KEY is set
if [ -z "$GEMINI_API_KEY" ]; then
    echo "✗ GEMINI_API_KEY environment variable is not set"
    exit 1
fi

# Check if DISCORD_WEBHOOK_URL is set
if [ -z "$DISCORD_WEBHOOK_URL" ]; then
    echo "! Warning: DISCORD_WEBHOOK_URL environment variable is not set"
fi

# Run the main Python script using venv
if "$VENV_PYTHON" "$PYTHON_SCRIPT"; then
    echo "✓ Python script executed successfully"
    
    # Check if Archive directory has changes
    cd "$SCRIPT_DIR"
    
    if git status --porcelain | grep -q "Archive/"; then
        echo "✓ Changes detected in Archive directory"
        
        # Add, commit, and push changes
        git add Archive/
        echo "✓ Added Archive/ changes to git"
        
        COMMIT_DATE=$(date +"%Y-%m-%d")
        git commit -m "docs: archive Hacker News digest [$COMMIT_DATE]"
        echo "✓ Committed changes"
        
        git push origin main
        echo "✓ Pushed to GitHub"
    else
        echo "! No changes detected in Archive directory"
    fi
    
    echo "========================================="
    echo "✓ Script completed successfully"
    echo "========================================="
    exit 0
else
    echo "✗ Python script execution failed"
    exit 1
fi
