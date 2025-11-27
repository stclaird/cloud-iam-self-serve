#!/bin/bash
# Apply AWS IAM configuration for a team
# Usage: ./apply.sh <team-name> [--dry-run]

set -e

TEAM=$1
DRY_RUN=$2

if [ -z "$TEAM" ]; then
    echo "Usage: ./apply.sh <team-name> [--dry-run]"
    echo ""
    echo "Example:"
    echo "  ./apply.sh example-team"
    echo "  ./apply.sh example-team --dry-run"
    exit 1
fi

cd "$(dirname "$0")"

echo "🚀 Applying AWS IAM configuration for team: $TEAM"
echo ""

# Validate first
echo "Step 1: Validating configuration..."
python validate.py "$TEAM"

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Validation failed. Please fix the errors and try again."
    exit 1
fi

echo ""
echo "Step 2: Applying IAM configuration..."
python apply.py "$TEAM" $DRY_RUN

echo ""
echo "✅ Done!"
