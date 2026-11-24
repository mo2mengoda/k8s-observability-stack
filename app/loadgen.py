"""Tiny load generator so the dashboards and alerts have traffic to show."""

import os
import time
import urllib.request

TARGET = os.getenv("TARGET", "http://localhost:8080/api/orders")
RPS = float(os.getenv("RPS", "5"))

while True:
    try:
        urllib.request.urlopen(TARGET, timeout=5).read()
    except Exception:
        pass  # errors are expected — they feed the error-rate alerts
    time.sleep(1 / RPS)
