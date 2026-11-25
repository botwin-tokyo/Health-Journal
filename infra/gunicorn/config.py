import os

appliance = os.environ.get("HEALTH03_ENV") == "production" and os.environ.get("HEALTH03_PI_APPLIANCE") == "1"
bind = "127.0.0.1:8010" if appliance else "127.0.0.1:8000"
workers = 2
threads = 2
timeout = 60
graceful_timeout = 30
max_requests = 1000
max_requests_jitter = 100
accesslog = None
errorlog = "-"
loglevel = "warning"
capture_output = False
forwarded_allow_ips = ""  # Only Django's secret-authenticated tunnel boundary trusts forwarding.
limit_request_line = 4094
limit_request_fields = 50
limit_request_field_size = 8190
