#!/bin/bash
# Quick start script for the control panel

echo "🎛️  Control Panel Setup"
echo "======================================"
echo ""

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Check if we're in the right directory
if [ ! -f "$SCRIPT_DIR/controlpanel_app.py" ]; then
    echo "❌ Error: controlpanel_app.py not found"
    echo "Please run this script from the control_panel directory"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv "$SCRIPT_DIR/venv"
    echo "✅ Virtual environment created"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source "$SCRIPT_DIR/venv/bin/activate"

# Check if dependencies are installed
echo "Checking dependencies..."
if python -c "import dash, dash_bootstrap_components, psutil, yaml" 2>/dev/null; then
    echo "✅ All dependencies installed"
else
    echo "📦 Installing dependencies..."
    pip install -r "$SCRIPT_DIR/requirements.txt"
    if [ $? -eq 0 ]; then
        echo "✅ Dependencies installed successfully"
    else
        echo "❌ Failed to install dependencies"
        exit 1
    fi
fi

echo ""
echo "======================================"
echo "🚀 Starting Control Panel..."
echo "======================================"
echo ""
echo "The control panel will be available at:"
echo "👉 http://localhost:8060"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start the app
python "$SCRIPT_DIR/controlpanel_app.py"
