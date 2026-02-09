#!/usr/bin/env bash
set -euo pipefail

if ! command -v aws >/dev/null 2>&1; then
  echo "[ssm] aws CLI not found. Install awscli and configure credentials."
  exit 1
fi

SSM_PATH="${SSM_PATH:-}"
OUT_FILE="${1:-.env}"

if [[ -z "$SSM_PATH" ]]; then
  echo "[ssm] Set SSM_PATH (e.g. /fitness-platform/prod/)."
  exit 1
fi

aws ssm get-parameters-by-path \
  --path "$SSM_PATH" \
  --with-decryption \
  --recursive \
  --query 'Parameters[*].[Name,Value]' \
  --output text \
  | awk -F'\t' '{
      name=$1;
      sub(".*/","",name);
      gsub("-","_",name);
      print name"="$2
    }' \
  | sort > "$OUT_FILE"

echo "[ssm] Wrote env to $OUT_FILE"
