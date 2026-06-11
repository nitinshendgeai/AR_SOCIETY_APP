#!/bin/sh
set -e

# Railway sets $PORT at runtime. Generate nginx.conf with the actual port
# before starting nginx. Using a heredoc so the shell expands $PORT while
# \$uri etc. remain as literal nginx variables.
cat > /etc/nginx/conf.d/default.conf << NGINX_EOF
server {
    listen $PORT;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript application/wasm;
    gzip_min_length 1024;

    location ~* \.(js|css|wasm|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        try_files \$uri =404;
    }

    location = /.env {
        expires 5m;
        add_header Cache-Control "no-store";
        try_files \$uri =404;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
        add_header Cache-Control "no-store, no-cache, must-revalidate";
    }
}
NGINX_EOF

echo "nginx: listening on port $PORT"
exec nginx -g 'daemon off;'
