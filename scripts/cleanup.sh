#!/bin/bash
# Cleanup expired temporary access for a team
# Usage: ./cleanup.sh <team-name> [--dry-run]

set -e

TEAM=$1
DRY_RUN=$2

if [ -z "$TEAM" ]; then
    echo "Usage: ./cleanup.sh <team-name> [--dry-run]"
    echo ""
    echo "Example:"
    echo "  ./cleanup.sh example-team"
    echo "  ./cleanup.sh example-team --dry-run"
    exit 1
fi

cd "$(dirname "$0")"

python cleanup.py "$TEAM" $DRY_RUN
