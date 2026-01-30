#!/bin/bash
# Quick test script for EditorWatch local development

echo "EditorWatch Local Test Setup"
echo "=============================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.11+"
    exit 1
fi
echo "✅ Python 3 found"

# Check Node
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js"
    exit 1
fi
echo "✅ Node.js found"

# Check Redis (optional for local testing)
if ! command -v redis-server &> /dev/null; then
    echo "⚠️  Redis not found (optional, analysis won't work locally)"
else
    echo "✅ Redis found"
fi

echo ""
echo "Setup Instructions:"
echo "==================="
echo ""
echo "1. Backend Setup:"
echo "   # From project root (editorwatch/)"
echo "   pip install -r requirements.txt"
echo "   export DATABASE_URL='sqlite:///editorwatch.db'"
echo "   export SECRET_KEY='test-secret'"
echo "   export ADMIN_USERNAME='admin'"
echo "   export ADMIN_PASSWORD='admin'"
echo "   python app.py"
echo ""
echo "2. Extension Setup (in new terminal):"
echo "   cd extension"
echo "   npm install"
echo "   # Then open extension/ folder in VS Code and press F5"
echo ""
echo "3. Test Assignment:"
echo "   mkdir test-assignment"
echo "   cp example.editorwatch test-assignment/.editorwatch"
echo "   # Edit .editorwatch to point to http://localhost:5000"
echo "   # Open test-assignment in VS Code"
echo ""
