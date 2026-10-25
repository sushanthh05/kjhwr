#!/bin/sh
set -e

# Default port to 80 if not set (Render provides PORT, e.g. 10000; local Docker uses 80)
export PORT="${PORT:-80}"

# Default BACKEND_URL to http://backend:8000 for local Docker Compose
export BACKEND_URL="${BACKEND_URL:-http://backend:8000}"

# Strip trailing slash if present
export BACKEND_URL="${BACKEND_URL%/}"

# If BACKEND_PORT is set and BACKEND_URL doesn't already contain a port:
if [ -n "$BACKEND_PORT" ] && ! echo "$BACKEND_URL" | grep -qE ':[0-9]+'; then
    export BACKEND_URL="${BACKEND_URL}:${BACKEND_PORT}"
fi

# Ensure BACKEND_URL starts with http:// or https://
if ! echo "$BACKEND_URL" | grep -qE '^https?://'; then
    export BACKEND_URL="http://$BACKEND_URL"
fi

# If BACKEND_URL still doesn't have a port and is an internal hostname (no dot in domain):
if ! echo "$BACKEND_URL" | grep -qE '(:[0-9]+|\.onrender\.com|\.com|\.net|\.org)'; then
    export BACKEND_URL="${BACKEND_URL}:8000"
fi

# Dynamically extract nameservers from /etc/resolv.conf for runtime DNS resolution
RESOLVER=$(awk 'BEGIN{ORS=" "} $1=="nameserver" {print $2}' /etc/resolv.conf)
export RESOLVER="${RESOLVER:-127.0.0.11 1.1.1.1 8.8.8.8}"

echo "Starting Nginx on port ${PORT} with backend ${BACKEND_URL} and DNS resolver ${RESOLVER}"

# Substitute only PORT, BACKEND_URL, and RESOLVER into Nginx config template
# Preserves standard Nginx variables ($host, $uri, $remote_addr, $proxy_add_x_forwarded_for, etc.)
envsubst '${PORT} ${BACKEND_URL} ${RESOLVER}' < /etc/nginx/nginx.conf.template > /etc/nginx/conf.d/default.conf

# Validate Nginx configuration syntax before starting
nginx -t

# Execute Nginx in foreground
exec nginx -g "daemon off;"
