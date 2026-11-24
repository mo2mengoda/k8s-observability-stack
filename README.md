# Kubernetes Observability Stack: SLOs, Alerting & Dashboards

Production-style monitoring for services running on an **on-prem Kubernetes cluster**, built on **Prometheus, Alertmanager and Grafana** (kube-prometheus-stack). It shows how I take a service from "no visibility" to **SLO-based alerting with runbooks**.

## What's inside

| Path | What it does |
|---|---|
| `app/` | `demo-api`: a Flask service instrumented with RED metrics (rate, errors, duration) via `prometheus_client`. Error rate and latency are tunable so alerts can be triggered on purpose. |
| `helm/kube-prometheus-stack-values.yaml` | Helm values for on-prem: persistent storage via StorageClass, cluster-wide ServiceMonitor discovery, Alertmanager routing (page vs. ticket), inhibition rules, Grafana behind ingress-nginx. |
| `alerts/slo-alerts.rules.yml` | **SLO: 99.5% availability / 30 days**. Recording rules plus **multi-window, multi-burn-rate alerts** (Google SRE Workbook): fast burn pages, slow burn opens a ticket. p95 latency and target-down alerts. |
| `alerts/k8s-platform.rules.yml` | Platform alerts: CrashLoopBackOff, pods not ready, replica mismatch, OOMKilled, NodeNotReady, disk predicted full within 24h, memory pressure, TLS expiry. |
| `dashboards/demo-api-slo.json` | Grafana dashboard: availability vs. SLO, **error budget remaining**, burn rate, request rate by status, error ratio vs. threshold, p50/p95/p99 latency. |
| `k8s/` | `demo-api` Deployment (probes, resources, non-root, read-only FS, zero-downtime rollout) + Service + **ServiceMonitor**. Rules and dashboard are packaged as `PrometheusRule` CRDs and a Grafana sidecar ConfigMap by `make k8s-manifests` (`scripts/build_manifests.py`). |
| `compose/` | The whole stack locally with one command, including a load generator. |
| `runbooks/` | Runbook linked from the alert annotations: triage, mitigate, verify, follow up. |

## Architecture

```
            ┌────────────── Kubernetes (on-prem) ──────────────┐
 users ───► │ ingress-nginx ─► demo-api (3 pods) ─► /metrics    │
            │                        ▲                         │
            │        ServiceMonitor  │ scrape 15s              │
            │                  ┌─────┴──────┐  rules  ┌──────────────┐
            │                  │ Prometheus │────────►│ Alertmanager │──► on-call (page)
            │                  └─────┬──────┘         └──────────────┘──► ticket queue
            │                        │ PromQL                  │
            │                  ┌─────▼──────┐                  │
            │                  │  Grafana   │  SLO dashboard   │
            │                  └────────────┘                  │
            └──────────────────────────────────────────────────┘
```

## SLO & alerting design

- **SLI:** ratio of non-5xx responses on `/api/*`.
- **SLO:** 99.5% over 30 days, so the **error budget is 0.5%**.
- **Fast burn (page):** burn rate above 14.4 over both 1h and 5m, which would spend 2% of the monthly budget in an hour.
- **Slow burn (ticket):** burn rate above 6 over both 6h and 30m.
- Using two windows means alerts fire quickly on real incidents and resolve quickly after recovery, without paging on short blips.
- Alertmanager routes `severity=page` to on-call, everything else to a ticket queue, and inhibits duplicate tickets while a page is firing.

## Run it locally

```bash
make up            # docker compose up -d --build
```
| | URL |
|---|---|
| demo-api | http://localhost:8080/api/orders |
| Prometheus | http://localhost:9090 (Alerts tab) |
| Grafana | http://localhost:3000 (admin / admin) → **SRE / demo-api — SLO & RED** |

To trigger the fast-burn alert, set `ERROR_RATE: "0.2"` in `compose/docker-compose.yml` and run `make up` again.

## Deploy on Kubernetes

```bash
make install-monitoring   # kube-prometheus-stack + PrometheusRules + dashboard
make deploy-app           # demo-api + ServiceMonitor
```
Change `storageClassName` in the Helm values to your cluster's storage (local-path, Longhorn, NFS, Ceph...).

## Tech
Kubernetes · Helm · Prometheus Operator · PromQL · Alertmanager · Grafana · Docker Compose · Python
