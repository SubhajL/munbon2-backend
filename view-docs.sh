#!/bin/bash
# View all auto-generated documentation

echo "=== Claude Code Auto-Generated Documentation ==="
echo

# 1. Project Structure
if [[ -f docs/PROJECT_STRUCTURE.md ]]; then
    echo "📁 Project Structure:"
    echo "-------------------"
    grep -A 5 "## Recent Changes" docs/PROJECT_STRUCTURE.md 2>/dev/null || echo "No recent changes"
    echo
fi

# 2. Port Configuration
if [[ -f docs/PORT_CONFIGURATION.md ]]; then
    echo "🔌 Service Ports:"
    echo "----------------"
    grep -E "^\|.*\|.*\|" docs/PORT_CONFIGURATION.md | head -10
    echo
fi

# 3. Current Tasks
if [[ -f docs/TASKS.md ]]; then
    echo "📋 Current Tasks:"
    echo "----------------"
    grep -E "^- \[[ x]\]" docs/TASKS.md | head -10
    echo
fi

# 4. Session Activity
SESSION_DIR="$HOME/.config/claude/project-docs/$(basename $(pwd))"
if [[ -d "$SESSION_DIR" ]]; then
    echo "🕐 Recent Session Activity:"
    echo "--------------------------"
    tail -5 "$SESSION_DIR/changes.log" 2>/dev/null || echo "No recent activity"
    echo
fi

echo "📍 Full Documentation Locations:"
echo "--------------------------------"
echo "• Project Structure: ./docs/PROJECT_STRUCTURE.md"
echo "• Port Config: ./docs/PORT_CONFIGURATION.md"
echo "• Tasks/TODOs: ./docs/TASKS.md"
echo "• Service Registry: ./docs/SERVICE_REGISTRY.json"
echo "• Session Logs: $SESSION_DIR/"
echo
echo "💡 Tip: These files update automatically as you work!"