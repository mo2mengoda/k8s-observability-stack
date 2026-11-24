.PHONY: up down k8s-manifests install-monitoring deploy-app lint

## Local demo (Docker Compose)
up:
	cd compose && docker compose up -d --build

down:
	cd compose && docker compose down -v

## Kubernetes
k8s-manifests:            ## regenerate PrometheusRules + dashboard ConfigMap
	python3 scripts/build_manifests.py

install-monitoring: k8s-manifests
	helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
	helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
	  -n monitoring --create-namespace -f helm/kube-prometheus-stack-values.yaml
	kubectl apply -f k8s/monitoring-rules-and-dashboards.yaml

deploy-app:
	kubectl apply -f k8s/demo-api.yaml

lint:                     ## needs promtool (ships with Prometheus)
	promtool check rules alerts/*.rules.yml
	promtool check config compose/prometheus.yml
