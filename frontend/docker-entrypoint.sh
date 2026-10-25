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

# On Render Free Tier, private inter-service networking is disabled.
# If BACKEND_URL is set to the internal hostname, automatically route to the live Render backend URL:
case "$BACKEND_URL" in
    *wind-forecast-backend*)
        export BACKEND_URL="https://wind-forecast-backend-yb3v.onrender.com"
        ;;
esac

# If BACKEND_URL still doesn't have a port and is an internal hostname (no dot in domain):
if ! echo "$BACKEND_URL" | grep -qE '(:[0-9]+|\.onrender\.com|\.com|\.net|\.org)'; then
    export BACKEND_URL="${BACKEND_URL}:8000"
fi


# Extract hostname and port for HTTP Host and TLS SNI headers
export BACKEND_HOST=$(echo "$BACKEND_URL" | sed -e 's|^https\?://||' -e 's|/.*$||')
export BACKEND_SNI=$(echo "$BACKEND_HOST" | sed -e 's|:.*$||')

# Dynamically extract nameservers from /etc/resolv.conf for runtime DNS resolution
RESOLVER=$(awk 'BEGIN{ORS=" "} $1=="nameserver" {print $2}' /etc/resolv.conf)
export RESOLVER="${RESOLVER:-127.0.0.11 1.1.1.1 8.8.8.8}"

echo "Starting Nginx on port ${PORT} with backend ${BACKEND_URL} (host: ${BACKEND_HOST}, sni: ${BACKEND_SNI}) and DNS resolver ${RESOLVER}"

# Substitute PORT, BACKEND_URL, BACKEND_HOST, BACKEND_SNI, and RESOLVER into Nginx config template
# Preserves standard Nginx variables ($host, $uri, $remote_addr, $proxy_add_x_forwarded_for, etc.)
envsubst '${PORT} ${BACKEND_URL} ${BACKEND_HOST} ${BACKEND_SNI} ${RESOLVER}' < /etc/nginx/nginx.conf.template > /etc/nginx/conf.d/default.conf

# Validate Nginx configuration syntax before starting
nginx -t

# Execute Nginx in foreground
exec nginx -g "daemon off;"
