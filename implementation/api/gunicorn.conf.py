"""Baseline for the Platform API image."""

bind = "0.0.0.0:8000"
workers = 2
worker_class = "sync"
timeout = 30
graceful_timeout = 30
preload_app = False

# Requests may carry account tokens. Keep request access logging off.
accesslog = None
errorlog = "-"

# Only Django's explicit trusted-proxy setting can interpret forwarded HTTPS.
forwarded_allow_ips = ""
secure_scheme_headers = {}
