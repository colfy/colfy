#!/bin/bash

# Crypto Battle Bot Data Backup Script

set -e

BACKUP_DIR="backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="crypto_battle_bot_backup_${TIMESTAMP}.tar.gz"

echo "💾 Creating backup of Crypto Battle Bot data..."

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Files to backup
FILES_TO_BACKUP=(
    "players.json"
    "battles.json"
    "deposit_addresses.json"
    "crypto_battle_bot.log"
    ".env"
)

# Create list of existing files
EXISTING_FILES=()
for file in "${FILES_TO_BACKUP[@]}"; do
    if [ -f "$file" ]; then
        EXISTING_FILES+=("$file")
        echo "📄 Found: $file"
    fi
done

if [ ${#EXISTING_FILES[@]} -eq 0 ]; then
    echo "⚠️  No data files found to backup."
    exit 0
fi

# Create backup
echo "📦 Creating backup archive: $BACKUP_FILE"
tar -czf "$BACKUP_DIR/$BACKUP_FILE" "${EXISTING_FILES[@]}"

echo "✅ Backup created successfully: $BACKUP_DIR/$BACKUP_FILE"

# Keep only last 10 backups
echo "🧹 Cleaning old backups (keeping last 10)..."
cd "$BACKUP_DIR"
ls -t crypto_battle_bot_backup_*.tar.gz | tail -n +11 | xargs -r rm --
cd ..

echo "💾 Backup completed!"

# Show backup info
BACKUP_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
echo "📊 Backup size: $BACKUP_SIZE"
echo "📁 Backup location: $BACKUP_DIR/$BACKUP_FILE"