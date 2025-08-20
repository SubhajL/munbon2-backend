#!/bin/bash
# View Claude Code conversations

CONV_DIR="/Users/subhajlimanond/dev/munbon2-backend/claude-conversations"
TODAY=$(date +%Y-%m-%d)

echo "=== Claude Code Conversations ==="
echo

# Show today's conversations
if [[ -f "$CONV_DIR/daily/conversations-$TODAY.md" ]]; then
    echo "📅 Today's Conversations:"
    echo "------------------------"
    tail -20 "$CONV_DIR/daily/conversations-$TODAY.md"
    echo
fi

# Show active sessions
echo "🔄 Recent Sessions:"
echo "------------------"
ls -lt "$CONV_DIR/sessions/" | grep -E "session-.*-$TODAY" | head -5

echo
echo "📁 Service Activity Today:"
echo "------------------------"
for service_file in "$CONV_DIR/by-service/"*-$TODAY.md; do
    if [[ -f "$service_file" ]]; then
        service=$(basename "$service_file" | sed "s/-$TODAY.md//")
        lines=$(wc -l < "$service_file" | tr -d ' ')
        echo "  • $service: $lines lines"
    fi
done

echo
echo "💡 Tips:"
echo "  - View full daily log: cat $CONV_DIR/daily/conversations-$TODAY.md"
echo "  - View specific service: cat $CONV_DIR/by-service/SERVICE-$TODAY.md"
echo "  - View session JSON: cat $CONV_DIR/sessions/session-*-$TODAY.json"