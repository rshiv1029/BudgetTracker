#!/bin/bash
echo "Starting the Finance App..."
# Get your local IP address for phone access
IP_ADDR=$(hostname -I | awk '{print $1}')
echo "Access from this PC: http://localhost:8000"
echo "Access from phone (same WIFI): http://$IP_ADDR:8000"
python app.py