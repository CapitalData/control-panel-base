#!/usr/bin/env python3
"""
Test script to verify control panel paths and configuration
"""
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent

print("🧪 Control Panel Configuration Test")
print("=" * 60)

# Configuration for apps
PYTHON_TOOLS = [
    {
        "id": "invoice-parser",
        "name": "Invoice Parser",
        "path": BASE_DIR / "invoice-parser" / "src" / "main.py",
        "type": "script",
        "description": "Parse invoice PDFs and extract data"
    },
    {
        "id": "invoice-generation",
        "name": "Invoice Generator",
        "path": BASE_DIR / "invoice_generation" / "Invoice_generator.ipynb",
        "type": "notebook",
        "description": "Generate invoices (Jupyter Notebook)"
    }
]

DASH_APPS = [
    {
        "id": "learning-platform",
        "name": "Learning Platform",
        "path": BASE_DIR / "learning_platform" / "app.py",
        "port": 8050,
        "description": "Educational platform with courses and materials"
    },
    {
        "id": "finance-tracker",
        "name": "Finance Tracker",
        "path": BASE_DIR / "finance_tracker" / "dash_app.py",
        "port": 8051,
        "description": "Financial tracking and visualization dashboard"
    },
    {
        "id": "dash-cards",
        "name": "Dash Cards Frontend",
        "path": BASE_DIR / "dash_cards_frontends" / "app.py",
        "port": 8052,
        "description": "Card-based UI components demo"
    }
]

print(f"\nBase Directory: {BASE_DIR}")
print(f"Exists: {BASE_DIR.exists()}")

print("\n📦 Python Tools:")
for tool in PYTHON_TOOLS:
    exists = "✅" if tool["path"].exists() else "❌"
    print(f"  {exists} {tool['name']}")
    print(f"     Path: {tool['path']}")
    print(f"     Type: {tool['type']}")
    print()

print("🎨 Dash Applications:")
for app in DASH_APPS:
    exists = "✅" if app["path"].exists() else "❌"
    print(f"  {exists} {app['name']}")
    print(f"     Path: {app['path']}")
    print(f"     Port: {app['port']}")
    print()

print("=" * 60)
print("✅ Configuration test complete!")
print("\nTo install dependencies:")
print("  pip3 install -r requirements.txt")
print("\nTo run the control panel:")
print("  python3 panel_app.py")
