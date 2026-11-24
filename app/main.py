"""
demo-api — a small instrumented service used to demonstrate SRE monitoring.

Exposes:
  GET /api/orders      business endpoint (simulated latency + errors)
  GET /healthz         liveness probe
  GET /readyz          readiness probe
  GET /metrics         Prometheus metrics (RED: Rate, Errors, Duration)

Error rate and latency can be tuned with env vars to trigger alerts on purpose:
  ERROR_RATE=0.05  LATENCY_MS=120
"""

import os
import random
import time

from flask import Flask, Response, jsonify, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

app = Flask(__name__)

ERROR_RATE = float(os.getenv("ERROR_RATE", "0.01"))
LATENCY_MS = int(os.getenv("LATENCY_MS", "80"))
VERSION = os.getenv("APP_VERSION", "1.0.0")

REQUESTS = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "route", "status"]
)
LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "route"],
    buckets=(0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
IN_FLIGHT = Gauge("http_requests_in_flight", "Requests currently being served")
BUILD_INFO = Gauge("app_build_info", "Build information", ["version"])
BUILD_INFO.labels(version=VERSION).set(1)


@app.before_request
def _start_timer():
    request._start = time.perf_counter()
    IN_FLIGHT.inc()


@app.after_request
def _record(response):
    IN_FLIGHT.dec()
    route = request.url_rule.rule if request.url_rule else "unmatched"
    if route != "/metrics":
        LATENCY.labels(request.method, route).observe(time.perf_counter() - request._start)
        REQUESTS.labels(request.method, route, str(response.status_code)).inc()
    return response


@app.get("/api/orders")
def orders():
    # jittered latency around LATENCY_MS
    time.sleep(max(0, random.gauss(LATENCY_MS, LATENCY_MS * 0.3)) / 1000)
    if random.random() < ERROR_RATE:
        return jsonify(error="upstream timeout"), 503
    return jsonify(orders=[{"id": i, "status": "shipped"} for i in range(3)])


@app.get("/healthz")
def healthz():
    return "ok"


@app.get("/readyz")
def readyz():
    return "ready"


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
