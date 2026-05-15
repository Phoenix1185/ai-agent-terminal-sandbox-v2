"""Monitoring and metrics"""

import time
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

from app.core.config import settings

# Metrics
REQUEST_COUNT = Counter(
    'app_requests_total',
    'Total requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'app_request_duration_seconds',
    'Request duration',
    ['method', 'endpoint']
)

ACTIVE_SESSIONS = Gauge(
    'app_active_sessions',
    'Active sessions',
    ['session_type']
)

SYSTEM_INFO = Info('app_build', 'Application build info')

SANDBOX_EXECUTIONS = Counter(
    'app_sandbox_executions_total',
    'Sandbox executions',
    ['language', 'status']
)

BROWSER_ACTIONS = Counter(
    'app_browser_actions_total',
    'Browser actions',
    ['action', 'status']
)

FILE_OPERATIONS = Counter(
    'app_file_operations_total',
    'File operations',
    ['operation', 'status']
)

TOOL_INSTALLATIONS = Counter(
    'app_tool_installations_total',
    'Tool installations',
    ['manager', 'status']
)

VOLUME_USAGE = Gauge(
    'app_volume_usage_bytes',
    'Volume usage in bytes',
    ['path']
)


def setup_monitoring():
    """Setup monitoring"""
    SYSTEM_INFO.info({
        'version': '2.0.0',
        'environment': settings.APP_ENV,
        'region': settings.FLY_REGION or 'local'
    })


def record_request(method: str, endpoint: str, status: int, duration: float):
    """Record request metrics"""
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
    REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)


def record_sandbox_execution(language: str, status: str):
    """Record sandbox execution"""
    SANDBOX_EXECUTIONS.labels(language=language, status=status).inc()


def record_browser_action(action: str, status: str):
    """Record browser action"""
    BROWSER_ACTIONS.labels(action=action, status=status).inc()


def record_file_operation(operation: str, status: str):
    """Record file operation"""
    FILE_OPERATIONS.labels(operation=operation, status=status).inc()


def record_tool_installation(manager: str, status: str):
    """Record tool installation"""
    TOOL_INSTALLATIONS.labels(manager=manager, status=status).inc()


def update_active_sessions(session_type: str, count: int):
    """Update active sessions gauge"""
    ACTIVE_SESSIONS.labels(session_type=session_type).set(count)


def update_volume_usage(path: str, used_bytes: int):
    """Update volume usage gauge"""
    VOLUME_USAGE.labels(path=path).set(used_bytes)
