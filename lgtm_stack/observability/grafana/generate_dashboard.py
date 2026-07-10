import json
from typing import Any, Dict, List

def build_loki_logging_dashboard() -> Dict[str, Any]:
    """Constructs a comprehensive Grafana Loki Logging dashboard JSON schema."""
    return {
        "title": "Application Logging (Loki)",
        "uid": "loki-logging-dash",
        "tags": ["loki", "logs", "as-code", "production"],
        "timezone": "browser",
        "schemaVersion": 38,
        "refresh": "5s",
        "panels": [
            # Row 1: KPI Statistics (Total Logs, Info, Warning, Error)
            _build_stat_panel(
                id=1,
                title="Total Logs (Last 1h)",
                expr='sum(count_over_time({container=~".*chaos-app.*|.*weather-service.*"}[1h]))',
                color_mode="value",
                threshold_steps=[
                    {"color": "blue", "value": None}
                ],
                x=0, y=0, w=6, h=4
            ),
            _build_stat_panel(
                id=2,
                title="Info Logs (Last 1h)",
                expr='sum(count_over_time({container=~".*chaos-app.*|.*weather-service.*", level="info"}[1h]))',
                color_mode="value",
                threshold_steps=[
                    {"color": "green", "value": None}
                ],
                x=6, y=0, w=6, h=4
            ),
            _build_stat_panel(
                id=3,
                title="Warning Logs (Last 1h)",
                expr='sum(count_over_time({container=~".*chaos-app.*|.*weather-service.*", level=~"warning|warn"}[1h]))',
                color_mode="value",
                threshold_steps=[
                    {"color": "orange", "value": None}
                ],
                x=12, y=0, w=6, h=4
            ),
            _build_stat_panel(
                id=4,
                title="Error Logs (Last 1h)",
                expr='sum(count_over_time({container=~".*chaos-app.*|.*weather-service.*", level=~"error|critical"}[1h]))',
                color_mode="background",
                threshold_steps=[
                    {"color": "green", "value": None},
                    {"color": "red", "value": 1}
                ],
                x=18, y=0, w=6, h=4
            ),

            # Row 2: HTTP Access Log KPI Statistics
            _build_stat_panel(
                id=5,
                title="HTTP Success (2xx/3xx)",
                expr='sum(count_over_time({container=~".*chaos-app.*|.*weather-service.*"} | json | status_code >= 200 and status_code < 400 [1h]))',
                color_mode="value",
                threshold_steps=[
                    {"color": "green", "value": None}
                ],
                x=0, y=4, w=8, h=4
            ),
            _build_stat_panel(
                id=6,
                title="HTTP Client Errors (4xx)",
                expr='sum(count_over_time({container=~".*chaos-app.*|.*weather-service.*"} | json | status_code >= 400 and status_code < 500 [1h]))',
                color_mode="value",
                threshold_steps=[
                    {"color": "orange", "value": None}
                ],
                x=8, y=4, w=8, h=4
            ),
            _build_stat_panel(
                id=7,
                title="HTTP Server Errors (5xx)",
                expr='sum(count_over_time({container=~".*chaos-app.*|.*weather-service.*"} | json | status_code >= 500 [1h]))',
                color_mode="background",
                threshold_steps=[
                    {"color": "green", "value": None},
                    {"color": "red", "value": 1}
                ],
                x=16, y=4, w=8, h=4
            ),

            # Row 3: Charts (Log severity trend and distribution)
            _build_log_severity_timeseries(id=8, x=0, y=8, w=16, h=8),
            _build_log_distribution_barchart(id=9, x=16, y=8, w=8, h=8),

            # Row 4: Real-time logging display
            _build_loki_logs_panel(id=10, x=0, y=16, w=24, h=10)
        ]
    }

def _build_stat_panel(
    id: int,
    title: str,
    expr: str,
    color_mode: str,
    threshold_steps: List[Dict[str, Any]],
    x: int,
    y: int,
    w: int,
    h: int
) -> Dict[str, Any]:
    """Helper to build consistent stat panels."""
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
                "color": {"mode": "thresholds"},
                "thresholds": {
                    "mode": "absolute",
                    "steps": threshold_steps
                }
            }
        }
    }

def _build_log_severity_timeseries(id: int, x: int, y: int, w: int, h: int) -> Dict[str, Any]:
    """Plots a stacked bar chart of log volumes separated by level."""
    return {
        "type": "timeseries",
        "title": "Log Severity Trend (Stacked Bars)",
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        "datasource": {"type": "loki", "uid": "loki"},
        "targets": [{
            "datasource": {"type": "loki", "uid": "loki"},
            "expr": 'sum by (level) (count_over_time({container=~".*chaos-app.*|.*weather-service.*"} [$__interval]))',
            "refId": "A",
            "legendFormat": "{{level}}"
        }],
        "options": {
            "tooltip": {"mode": "multi"},
            "legend": {"displayMode": "table", "placement": "right"}
        },
        "fieldConfig": {
            "defaults": {
                "custom": {
                    "drawStyle": "bars",
                    "fillOpacity": 80,
                    "lineWidth": 0,
                    "stacking": {"group": "A", "mode": "normal"}
                }
            }
        }
    }

def _build_log_distribution_barchart(id: int, x: int, y: int, w: int, h: int) -> Dict[str, Any]:
    """Plots a bar chart showing total log counts per severity level."""
    return {
        "type": "barchart",
        "title": "Log Severity Distribution",
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        "datasource": {"type": "loki", "uid": "loki"},
        "targets": [{
            "datasource": {"type": "loki", "uid": "loki"},
            "expr": 'sum by (level) (count_over_time({container=~".*chaos-app.*|.*weather-service.*"} [$__range]))',
            "refId": "A",
            "legendFormat": "{{level}}"
        }],
        "options": {
            "orientation": "horizontal",
            "showValue": "always",
            "stacking": "none"
        }
    }

def _build_loki_logs_panel(id: int, x: int, y: int, w: int, h: int) -> Dict[str, Any]:
    """Live streaming log output with format and details."""
    return {
        "type": "logs",
        "title": "Real-time Application Logs",
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        "datasource": {"type": "loki", "uid": "loki"},
        "targets": [{
            "datasource": {"type": "loki", "uid": "loki"},
            "expr": '{container=~".*chaos-app.*|.*weather-service.*"} | json',
            "refId": "A"
        }],
        "options": {
            "showTime": True,
            "showLabels": True,
            "wrapLogMessage": True,
            "enableLogDetails": True,
            "prettifyJson": True
        }
    }

def main() -> None:
    dashboard_json = build_loki_logging_dashboard()
    filename = "loki_dashboard.json"
    
    with open(filename, "w") as f:
        json.dump(dashboard_json, f, indent=2)
        
    print(f"Success: Loki Logging Dashboard generated and saved to {filename}")

if __name__ == "__main__":
    main()