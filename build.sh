#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python scripts/generate_app_icons.py
python manage.py collectstatic --no-input
python manage.py migrate