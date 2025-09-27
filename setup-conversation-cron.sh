#!/bin/bash
# Setup cron job for automatic conversation export

SCRIPT_PATH="/Users/subhajlimanond/dev/munbon2-backend/export-claude-conversations.sh"
CRON_LOG="/Users/subhajlimanond/dev/munbon2-backend/claude-conversations/cron.log"

echo "Setting up cron job for Claude conversation export..."

# Create cron entry (runs every hour)
CRON_ENTRY="0 * * * * $SCRIPT_PATH >> $CRON_LOG 2>&1"

# Check if cron entry already exists
if crontab -l 2>/dev/null | grep -q "$SCRIPT_PATH"; then
    echo "Cron job already exists!"
else
    # Add to crontab
    (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
    echo "Cron job added successfully!"
fi

echo
echo "Current crontab:"
crontab -l | grep claude

echo
echo "The export script will run every hour and save conversations to:"
echo "  /Users/subhajlimanond/dev/munbon2-backend/claude-conversations/exported/"
echo
echo "To run manually: $SCRIPT_PATH"
echo "To remove cron: crontab -e (and delete the line)"
echo "To check logs: tail -f $CRON_LOG"