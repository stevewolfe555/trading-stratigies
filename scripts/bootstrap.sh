#!/usr/bin/env bash
set -euo pipefail

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
else
  echo ".env already exists"
fi

echo "Bootstrap complete. Next:"
echo "1) Edit .env (set API keys)"
echo "2) Run: make up"
echo "3) Tail logs: make logs"
