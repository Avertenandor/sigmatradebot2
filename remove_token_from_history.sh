#!/bin/bash
# Script to remove bot token from Git history
# WARNING: This rewrites history. Use with caution!

TOKEN="8490693145:AAEECwr4c-S-PuHVIccFCw4mMpH0-Uq_rhs"
REPLACEMENT="YOUR_BOT_TOKEN_HERE"

echo "Removing token from Git history..."
echo "This may take a while..."

# Use git filter-branch to replace token in all commits
git filter-branch --force --tree-filter "
if [ -f SERVER_ACCESS.md ]; then
    sed -i 's/$TOKEN/$REPLACEMENT/g' SERVER_ACCESS.md
fi
" --prune-empty --tag-name-filter cat -- --all

echo "Done! Token removed from history."
echo "Next steps:"
echo "1. Verify: git log -p -S '8490693145' (should return nothing)"
echo "2. Force push: git push --force --all"
echo "3. Force push tags: git push --force --tags"

