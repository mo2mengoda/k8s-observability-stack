"""Generates the Grafana dashboard JSON and the Kubernetes wrappers (ConfigMap + PrometheusRule)."""
import json
import yaml
from pathlib import Path

root = Path(__file__).resolve().parents[1]
DS = {"type": "prometheus", "uid": "${datasource}"}
SLO = 0.995


def ts(id_, title, exprs, x, y, w=12, h=8, unit="short", thresholds=None):
    p = {
        "id": id_, "type": "timeseries", "title": title, "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "fieldConfig": {"defaults": {"unit": unit}, "overrides": []},
        "targets": [{"refId": chr(65 + i), "expr": e, "legendFormat": l, "datasource": DS}
                    for i, (e, l) in enumerate(exprs)],
    }
    if thresholds:
        p["fieldConfig"]["defaults"]["thresholds"] = {"mode": "absolute", "steps": thresholds}
        p["fieldConfig"]["defaults"]["custom"] = {"thresholdsStyle": {"mode": "line"}}
    return p


def stat(id_, title, expr, x, unit, steps, decimals=3):
    return {
        "id": id_, "type": "stat", "title": title, "datasource": DS,
        "gridPos": {"x": x, "y": 0, "w": 6, "h": 5},
        "fieldConfig": {"defaults": {"unit": unit, "decimals": decimals,
                                     "thresholds": {"mode": "absolute", "steps": steps}}},
        "options": {"colorMode": "background", "reduceOptions": {"calcs": ["lastNotNull"]}},
        "targets": [{"refId": "A", "expr": expr, "datasource": DS}],
    }


ok_ratio_30d = ('1 - (sum(increase(http_requests_total{route=~"/api/.*",status=~"5.."}[30d]))'
                ' / sum(increase(http_requests_total{route=~"/api/.*"}[30d])))')

dashboard = {
    "uid": "demo-api-slo",
    "title": "demo-api — SLO & RED",
    "tags": ["sre", "slo", "kubernetes"],
    "timezone": "browser",
    "schemaVersion": 39,
    "refresh": "30s",
    "time": {"from": "now-6h", "to": "now"},
    "templating": {"list": [{"name": "datasource", "type": "datasource", "query": "prometheus",
                             "current": {"text": "Prometheus", "value": "prometheus"}}]},
    "panels": [
        stat(1, "Availability (30d) — SLO 99.5%", ok_ratio_30d, 0, "percentunit",
             [{"color": "red", "value": None}, {"color": "orange", "value": 0.99},
              {"color": "green", "value": SLO}]),
        stat(2, "Error budget remaining (30d)",
             f"1 - ((1 - ({ok_ratio_30d})) / {1 - SLO:.3f})", 6, "percentunit",
             [{"color": "red", "value": None}, {"color": "orange", "value": 0.25},
              {"color": "green", "value": 0.5}], 1),
        stat(3, "Burn rate (1h)", f"slo:http_error_ratio:rate1h / {1 - SLO:.3f}", 12, "none",
             [{"color": "green", "value": None}, {"color": "orange", "value": 6},
              {"color": "red", "value": 14.4}], 1),
        stat(4, "Requests / sec", 'sum(rate(http_requests_total{route=~"/api/.*"}[5m]))', 18, "reqps",
             [{"color": "blue", "value": None}], 1),
        ts(5, "Request rate by status",
           [('sum by (status) (rate(http_requests_total{route=~"/api/.*"}[5m]))', "{{status}}")],
           0, 5, unit="reqps"),
        ts(6, "Error ratio vs. fast-burn threshold",
           [("slo:http_error_ratio:rate5m", "5m"), ("slo:http_error_ratio:rate1h", "1h")],
           12, 5, unit="percentunit",
           thresholds=[{"color": "green", "value": None}, {"color": "red", "value": round(14.4 * (1 - SLO), 4)}]),
        ts(7, "Latency p50 / p95 / p99",
           [(f'histogram_quantile({q}, sum by (le) (rate(http_request_duration_seconds_bucket{{route=~"/api/.*"}}[5m])))', f"p{int(q*100)}")
            for q in (0.5, 0.95, 0.99)],
           0, 13, unit="s",
           thresholds=[{"color": "green", "value": None}, {"color": "red", "value": 0.5}]),
        ts(8, "In-flight requests & pods up",
           [("sum(http_requests_in_flight)", "in-flight"), ('sum(up{job=~"demo-api.*"})', "targets up")],
           12, 13),
    ],
}

(root / "dashboards" / "demo-api-slo.json").write_text(json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n")

# ---- Kubernetes wrappers -------------------------------------------------
cm = {
    "apiVersion": "v1", "kind": "ConfigMap",
    "metadata": {"name": "grafana-dashboard-demo-api", "namespace": "monitoring",
                 "labels": {"grafana_dashboard": "1"}},
    "data": {"demo-api-slo.json": json.dumps(dashboard, indent=2)},
}
docs = [cm]
for f in ("slo-alerts.rules.yml", "k8s-platform.rules.yml"):
    spec = yaml.safe_load((root / "alerts" / f).read_text())
    docs.append({
        "apiVersion": "monitoring.coreos.com/v1", "kind": "PrometheusRule",
        "metadata": {"name": f.replace(".rules.yml", ""), "namespace": "monitoring",
                     "labels": {"release": "monitoring"}},
        "spec": spec,
    })


def lit_rep(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|" if "\n" in data else None)


yaml.add_representer(str, lit_rep)
header = "# Generated from ../alerts and ../dashboards by `make k8s-manifests` — do not edit by hand.\n"
(root / "k8s" / "monitoring-rules-and-dashboards.yaml").write_text(
    header + yaml.dump_all(docs, sort_keys=False, width=200))
print("ok")
