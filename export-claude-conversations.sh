#!/bin/bash
# Export Claude conversations from native JSONL files

PROJECT_ROOT="/Users/subhajlimanond/dev/munbon2-backend"
CLAUDE_PROJECT_DIR="$HOME/.claude/projects/-Users-subhajlimanond-dev-munbon2-backend"
EXPORT_DIR="$PROJECT_ROOT/claude-conversations/exported"
TODAY=$(date +%Y-%m-%d)

# Create export directory
mkdir -p "$EXPORT_DIR/daily"
mkdir -p "$EXPORT_DIR/by-session"

echo "=== Exporting Claude Conversations ==="
echo "Date: $TODAY"
echo

# Function to parse JSONL and extract conversation
parse_conversation() {
    local jsonl_file="$1"
    local session_id=$(basename "$jsonl_file" .jsonl)
    local output_file="$EXPORT_DIR/by-session/session-$session_id.md"
    
    echo "Processing session: $session_id"
    
    # Create markdown file with session header
    {
        echo "# Claude Conversation Session: $session_id"
        echo "Generated: $(date)"
        echo "---"
        echo
    } > "$output_file"
    
    # Parse JSONL file and extract messages
    while IFS= read -r line; do
        # Extract message type
        msg_type=$(echo "$line" | jq -r '.type // "unknown"')
        timestamp=$(echo "$line" | jq -r '.timestamp // "no-timestamp"')
        
        case "$msg_type" in
            "user")
                # Extract user message
                content=$(echo "$line" | jq -r '.message.content[0].content // empty' 2>/dev/null)
                if [[ -n "$content" ]]; then
                    {
                        echo "## User ($timestamp)"
                        echo "$content"
                        echo
                    } >> "$output_file"
                fi
                
                # Check for tool results
                tool_result=$(echo "$line" | jq -r '.toolUseResult.stdout // empty' 2>/dev/null)
                if [[ -n "$tool_result" ]]; then
                    {
                        echo "### Tool Result:"
                        echo '```'
                        echo "$tool_result" | head -20
                        echo '```'
                        echo
                    } >> "$output_file"
                fi
                ;;
                
            "assistant")
                # Extract assistant response
                content=$(echo "$line" | jq -r '.message.content[0].text // empty' 2>/dev/null)
                if [[ -n "$content" ]]; then
                    {
                        echo "## Assistant ($timestamp)"
                        echo "$content"
                        echo
                    } >> "$output_file"
                fi
                
                # Check for tool uses
                tool_name=$(echo "$line" | jq -r '.message.content[0].name // empty' 2>/dev/null)
                if [[ -n "$tool_name" && "$tool_name" != "null" ]]; then
                    tool_input=$(echo "$line" | jq -r '.message.content[0].input' 2>/dev/null)
                    {
                        echo "### Tool Use: $tool_name"
                        echo '```json'
                        echo "$tool_input" | jq . 2>/dev/null || echo "$tool_input"
                        echo '```'
                        echo
                    } >> "$output_file"
                fi
                ;;
        esac
    done < "$jsonl_file"
    
    # Also append to daily log
    cat "$output_file" >> "$EXPORT_DIR/daily/conversations-$TODAY.md"
    echo "---" >> "$EXPORT_DIR/daily/conversations-$TODAY.md"
}

# Process today's conversation files
echo "Looking for conversation files from today..."
find "$CLAUDE_PROJECT_DIR" -name "*.jsonl" -mtime -1 -type f | while read -r jsonl_file; do
    parse_conversation "$jsonl_file"
done

# Create summary
TOTAL_SESSIONS=$(find "$EXPORT_DIR/by-session" -name "*.md" -mtime -1 | wc -l)
echo
echo "Export complete!"
echo "- Total sessions exported: $TOTAL_SESSIONS"
echo "- Daily log: $EXPORT_DIR/daily/conversations-$TODAY.md"
echo "- Session logs: $EXPORT_DIR/by-session/"

# Optional: Show recent activity
echo
echo "Recent conversation activity:"
tail -50 "$EXPORT_DIR/daily/conversations-$TODAY.md" 2>/dev/null || echo "No conversations exported yet"