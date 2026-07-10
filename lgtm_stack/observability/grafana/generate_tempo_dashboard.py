import json
from typing import Any, Dict, List

def build_tempo_traces_dashboard() -> Dict[str, Any]:
    """Constructs a comprehensive Grafana Tempo Tracing dashboard JSON schema."""
    return {
        "title": "Application Tracing (Tempo)",
        "uid": "tempo-traces-dash",
        "tags": ["tempo", "traces", "as-code", "production"],
        "timezone": "browser",
        "schemaVersion": 38,
        "refresh": "10s",
        "panels": [
            # Row 1: Trace KPI Statistics (derived from access logs)
            _build_stat_panel(
                id=1,
                title="Total Traces (Last 1h)",
                expr='sum(count_over_time({container=~".*chaos-app.*|.*weather-service.*"} | json | status_code > 0 [1h]))',
                unit="none",
                color_mode="value",
                threshold_steps=[{"color": "blue", "value": None}],
                x=0, y=0, w=6, h=4
            ),
            _build_stat_panel(
                id=2,
                title="Avg Trace Duration (Last 1h)",
                expr='avg_over_time({container=~".*chaos-app.*|.*weather-service.*"} | json | unwrap duration_ms [1h])',
                unit="ms",
                color_mode="value",
                threshold_steps=[{"color": "green", "value": None}],
                x=6, y=0, w=6, h=4
            ),
            _build_stat_panel(
                id=3,
                title="p95 Trace Duration (Last 1h)",
                expr='quantile_over_time(0.95, {container=~".*chaos-app.*|.*weather-service.*"} | json | unwrap duration_ms [1h])',
                unit="ms",
                color_mode="value",
                threshold_steps=[
                    {"color": "green", "value": None},
                    {"color": "orange", "value": 150},
                    {"color": "red", "value": 500}
                ],
                x=12, y=0, w=6, h=4
            ),
            _build_stat_panel(
                id=4,
                title="Failed Traces (Last 1h)",
                expr='sum(count_over_time({container=~".*chaos-app.*|.*weather-service.*"} | json | status_code >= 500 [1h]))',
                unit="none",
                color_mode="background",
                threshold_steps=[
                    {"color": "green", "value": None},
                    {"color": "red", "value": 1}
                ],
                x=18, y=0, w=6, h=4
            ),

            # Row 2: Service Dependency Graph (Node Graph)
            _build_tempo_nodegraph_panel(
                id=11,
                title="Service Dependency & Communication Graph",
                x=0, y=4, w=24, h=8
            ),

            # Row 3: Performance Trends over time
            _build_trace_latency_timeseries(id=5, x=0, y=12, w=12, h=8),
            _build_trace_rate_timeseries(id=6, x=12, y=12, w=12, h=8),

            # Row 4: Trace Discovery / Lists (Tempo TraceQL)
            _build_tempo_table_panel(
                id=7,
                title="Slow Traces (>100ms)",
                query='{ .service.name = "chaos-service" || .service.name = "weather-service" } | duration > 100ms',
                x=0, y=20, w=12, h=6
            ),
            _build_tempo_table_panel(
                id=8,
                title="Traces with Errors",
                query='{ .service.name = "chaos-service" || .service.name = "weather-service" } | status.code = "error" || .http.status_code >= 500',
                x=12, y=20, w=12, h=6
            ),

            # Row 5: Microservices communication & internals (Tempo TraceQL)
            _build_tempo_table_panel(
                id=9,
                title="Inter-Service Traces: Chaos -> Weather",
                query='{ .service.name = "chaos-service" } >> { .service.name = "weather-service" }',
                x=0, y=26, w=12, h=6
            ),
            _build_tempo_table_panel(
                id=10,
                title="Weather Service Internal Latency (>50ms)",
                query='{ .service.name = "weather-service" } | duration > 50ms',
                x=12, y=26, w=12, h=6
            )
        ]
    }

def _build_stat_panel(
    id: int,
    title: str,
    expr: str,
    unit: str,
    color_mode: str,
    threshold_steps: List[Dict[str, Any]],
    x: int,
    y: int,
    w: int,
    h: int
) -> Dict[str, Any]:
    """Helper to build consistent stat panels using LogQL for trace metrics."""
    return {
        "type": "stat",
        "title": title,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        "datasource": {"type": "loki", "uid": "loki"},
        "targets": [{
            "datasource": {"type": "loki", "uid": "loki"},
            "expr": expr,
            "refId": "A"
        }],
        "options": {
            "colorMode": color_mode,
            "graphMode": "sparkline",
            "justifyMode": "auto"
        },
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "color": {"mode": "thresholds"},
                "thresholds": {
                    "mode": "absolute",
                    "steps": threshold_steps
                }
            }
        }
    }

def _build_tempo_nodegraph_panel(id: int, title: str, x: int, y: int, w: int, h: int) -> Dict[str, Any]:
    """Builds a Node Graph panel mapping service communication from Tempo's Service Map."""
    return {
        "type": "nodeGraph",
        "title": title,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        "datasource": {"type": "tempo", "uid": "tempo"},
        "targets": [{
            "datasource": {"type": "tempo", "uid": "tempo"},
            "queryType": "serviceMap",
            "refId": "A"
        }],
        "options": {}
    }

def _build_trace_latency_timeseries(id: int, x: int, y: int, w: int, h: int) -> Dict[str, Any]:
    """Plots request/trace latency percentiles over time."""
    return {
        "type": "timeseries",
        "title": "Trace Latency Percentiles (p50, p90, p95, p99)",
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        "datasource": {"type": "loki", "uid": "loki"},
        "targets": [
            {
                "datasource": {"type": "loki", "uid": "loki"},
                "expr": 'quantile_over_time(0.50, {container=~".*chaos-app.*|.*weather-service.*"} | json | unwrap duration_ms [$__interval])',
                "refId": "A",
                "legendFormat": "p50"
            },
            {
                "datasource": {"type": "loki", "uid": "loki"},
                "expr": 'quantile_over_time(0.90, {container=~".*chaos-app.*|.*weather-service.*"} | json | unwrap duration_ms [$__interval])',
                "refId": "B",
                "legendFormat": "p90"
            },
            {
                "datasource": {"type": "loki", "uid": "loki"},
                "expr": 'quantile_over_time(0.95, {container=~".*chaos-app.*|.*weather-service.*"} | json | unwrap duration_ms [$__interval])',
                "refId": "C",
                "legendFormat": "p95"
            },
            {
                "datasource": {"type": "loki", "uid": "loki"},
                "expr": 'quantile_over_time(0.99, {container=~".*chaos-app.*|.*weather-service.*"} | json | unwrap duration_ms [$__interval])',
                "refId": "D",
                "legendFormat": "p99"
            }
        ],
        "options": {
            "tooltip": {"mode": "multi"},
            "legend": {"displayMode": "table", "placement": "right"}
        },
        "fieldConfig": {
            "defaults": {
                "unit": "ms",
                "custom": {
                    "drawStyle": "line",
                    "lineInterpolation": "smooth",
                    "fillOpacity": 10
                }
            }
        }
    }

def _build_trace_rate_timeseries(id: int, x: int, y: int, w: int, h: int) -> Dict[str, Any]:
    """Plots trace start/generation rate by service."""
    return {
        "type": "timeseries",
        "title": "Trace Generation Rate by Service",
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        "datasource": {"type": "loki", "uid": "loki"},
        "targets": [{
            "datasource": {"type": "loki", "uid": "loki"},
            "expr": 'sum by (container) (rate({container=~".*chaos-app.*|.*weather-service.*"} | json | status_code > 0 [$__interval]))',
            "refId": "A",
            "legendFormat": "{{container}}"
        }],
        "options": {
            "tooltip": {"mode": "multi"},
            "legend": {"displayMode": "table", "placement": "right"}
        },
        "fieldConfig": {
            "defaults": {
                "unit": "requests/sec",
                "custom": {
                    "drawStyle": "line",
                    "lineInterpolation": "smooth",
                    "fillOpacity": 15
                }
            }
        }
    }

def _build_tempo_table_panel(id: int, title: str, query: str, x: int, y: int, w: int, h: int) -> Dict[str, Any]:
    """Builds a Table panel displaying traces matching a TraceQL query, with clickable links to open trace details."""
    return {
        "type": "table",
        "title": title,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        "datasource": {"type": "tempo", "uid": "tempo"},
        "targets": [{
            "datasource": {"type": "tempo", "uid": "tempo"},
            "queryType": "traceql",
            "query": query,
            "refId": "A"
        }],
        "options": {
            "showHeader": True,
            "sortBy": [{"displayName": "Start time", "desc": True}]
        },
        "fieldConfig": {
            "defaults": {},
            "overrides": [
                {
                    "matcher": {
                        "id": "byName",
                        "options": "traceID"
                    },
                    "properties": [
                        {
                            "id": "links",
                            "value": [
                                {
                                    "title": "Open Trace Details",
                                    "url": "/explore?orgId=1&left=%5B%22now-1h%22,%22now%22,%22tempo%22,%7B%22query%22:%22${__value.raw}%22%7D%5D",
                                    "targetBlank": True
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    }

def main() -> None:
    dashboard_json = build_tempo_traces_dashboard()
    filename = "tempo_dashboard.json"
    
    with open(filename, "w") as f:
        json.dump(dashboard_json, f, indent=2)
        
    print(f"Success: Tempo Tracing Dashboard generated and saved to {filename}")

if __name__ == "__main__":
    main()
