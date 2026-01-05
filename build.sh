#!/bin/bash
# Vercel Build Script
# This script runs during Vercel build to set up the Django app

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Build complete!"
