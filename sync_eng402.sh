#!/bin/bash

SOURCE="/home/pi/eng402_gateway_data"
USB_MOUNT="/mnt/eng402_usb"
TODAY="$(date +%F)"
DEST="$USB_MOUNT/ENG402_Backup/$TODAY"
LOG_FILE="$SOURCE/logs/usb_sync.log"

mkdir -p \
    "$SOURCE/raw" \
    "$SOURCE/status" \
    "$SOURCE/processed" \
    "$SOURCE/figures" \
    "$SOURCE/logs" \
    "$SOURCE/code" \
    "$SOURCE/config" \
    "$SOURCE/errors"

if ! mountpoint -q "$USB_MOUNT"; then
    /usr/bin/sudo /bin/mount "$USB_MOUNT"
fi

if ! mountpoint -q "$USB_MOUNT"; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') USB not mounted; auto-mount failed." >> "$LOG_FILE"
    exit 0
fi
mkdir -p \
    "$DEST/raw" \
    "$DEST/status" \
    "$DEST/processed" \
    "$DEST/figures" \
    "$DEST/logs" \
    "$DEST/code" \
    "$DEST/config" \
    "$DEST/errors"

rsync -rtv \
    --modify-window=1 \
    --no-perms \
    --no-owner \
    --no-group \
    "$SOURCE/raw/"*"$TODAY"* \
    "$DEST/raw/" 2>/dev/null || true

if [ -f "$SOURCE/raw/sensor_data.csv" ]; then
    rsync -rtv \
        --modify-window=1 \
        --no-perms \
        --no-owner \
        --no-group \
        "$SOURCE/raw/sensor_data.csv" \
        "$DEST/raw/"
fi

rsync -rtv \
    --modify-window=1 \
    --no-perms \
    --no-owner \
    --no-group \
    "$SOURCE/status/"*"$TODAY"* \
    "$DEST/status/" 2>/dev/null || true

rsync -rtv \
    --modify-window=1 \
    --no-perms \
    --no-owner \
    --no-group \
    "$SOURCE/processed/" \
    "$DEST/processed/"

rsync -rtv \
    --modify-window=1 \
    --no-perms \
    --no-owner \
    --no-group \
    "$SOURCE/figures/" \
    "$DEST/figures/"

rsync -rtv \
    --modify-window=1 \
    --no-perms \
    --no-owner \
    --no-group \
    "$SOURCE/logs/" \
    "$DEST/logs/"

rsync -rtv \
    --modify-window=1 \
    --no-perms \
    --no-owner \
    --no-group \
    --exclude=".*.swp" \
    --exclude="*~" \
    --exclude="__pycache__/" \
    "$SOURCE/code/" \
    "$DEST/code/"

rsync -rtv \
    --modify-window=1 \
    --no-perms \
    --no-owner \
    --no-group \
    "$SOURCE/config/" \
    "$DEST/config/"

rsync -rtv \
    --modify-window=1 \
    --no-perms \
    --no-owner \
    --no-group \
    "$SOURCE/errors/" \
    "$DEST/errors/"

echo "$(date '+%Y-%m-%d %H:%M:%S') Sync completed to $DEST" >> "$LOG_FILE"
