# Runbook: ErrorBudgetFastBurn / ErrorBudgetSlowBurn (demo-api)

**SLO:** 99.5% of `/api/*` requests return non-5xx over 30 days (error budget 0.5%).
**Fast burn (page):** error ratio > 7.2% over 1h *and* 5m — budget gone in ~2 days.
**Slow burn (ticket):** error ratio > 3% over 6h *and* 30m.

## 1. Triage (first 5 minutes)
1. Open Grafana → **SRE / demo-api — SLO & RED**. Is the error ratio still climbing or already recovering?
2. Check whether a deploy just happened:
   ```bash
   kubectl -n demo rollout history deploy/demo-api
   argocd app history demo-api-prod
   ```
3. Check pod health:
   ```bash
   kubectl -n demo get pods -l app=demo-api -o wide
   kubectl -n demo describe pod <pod>      # restarts, OOMKilled, probes failing?
   kubectl -n demo logs <pod> --previous   # logs from the crashed container
   ```

## 2. Mitigate (stop the bleeding before root-causing)
| Symptom | Action |
|---|---|
| Started right after a deploy | Roll back: `argocd app rollback demo-api-prod` or `kubectl -n demo rollout undo deploy/demo-api` |
| One pod/node bad, others fine | `kubectl -n demo delete pod <pod>`; cordon the node if it's the node |
| All pods saturated (CPU/latency high) | Scale out: `kubectl -n demo scale deploy/demo-api --replicas=6` |
| Upstream dependency failing | Confirm in logs, escalate to the owning team, consider feature flag / fallback |

## 3. Verify
- Error ratio back under 0.5% on the dashboard for 15 minutes.
- Alert resolves in Alertmanager.

## 4. Follow up
- Record the timeline (detection, mitigation, recovery) while it's fresh.
- Write a blameless postmortem if the page fired or > 10% of the monthly budget was consumed.
- Add an action item for every contributing cause (missing test, missing alert, unsafe rollout...).
