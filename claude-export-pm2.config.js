module.exports = {
  apps: [{
    name: 'claude-conversation-export',
    script: '/Users/subhajlimanond/dev/munbon2-backend/export-claude-conversations.sh',
    instances: 1,
    cron_restart: '0 * * * *', // Every hour
    autorestart: false,
    watch: false,
    max_memory_restart: '100M',
    error_file: '/Users/subhajlimanond/dev/munbon2-backend/claude-conversations/pm2-error.log',
    out_file: '/Users/subhajlimanond/dev/munbon2-backend/claude-conversations/pm2-out.log',
    log_file: '/Users/subhajlimanond/dev/munbon2-backend/claude-conversations/pm2-combined.log',
    time: true
  }]
};