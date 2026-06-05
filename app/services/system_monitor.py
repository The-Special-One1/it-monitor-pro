"""
System Monitor Service
======================

Provides real-time system metrics collection using psutil.
Designed for IT infrastructure monitoring and incident detection.

Author: Santo António
Project: IT Monitor Pro
"""

import socket
import psutil
from datetime import datetime
from typing import Dict, Any


class SystemMonitor:
    """
    Collects real-time system metrics from the host machine.

    This class encapsulates all system monitoring logic, providing
    a clean API for retrieving CPU, memory, disk, and network metrics.

    Designed to be stateless and thread-safe for use in REST API endpoints.

    Example:
        >>> monitor = SystemMonitor()
        >>> snapshot = monitor.get_snapshot()
        >>> print(snapshot['cpu']['usage_percent'])
        23.5
    """

    # ============================================================
    # THRESHOLDS (percentage)
    # ============================================================

    CPU_WARNING_THRESHOLD = 75.0
    CPU_CRITICAL_THRESHOLD = 90.0

    MEMORY_WARNING_THRESHOLD = 80.0
    MEMORY_CRITICAL_THRESHOLD = 95.0

    DISK_WARNING_THRESHOLD = 80.0
    DISK_CRITICAL_THRESHOLD = 90.0

    # ============================================================
    # CONSTRUCTOR & HELPERS
    # ============================================================

    def __init__(self) -> None:
        """Initialize the system monitor."""
        self._hostname = self._get_hostname()

    @staticmethod
    def _get_hostname() -> str:
        """Return the hostname of the machine."""
        return socket.gethostname()

    @staticmethod
    def _classify_status(value: float, warning: float, critical: float) -> str:
        """
        Classify a metric value as OK, WARNING, or CRITICAL.

        Args:
            value: The metric value (percentage).
            warning: The warning threshold.
            critical: The critical threshold.

        Returns:
            'OK', 'WARNING', or 'CRITICAL'.
        """
        if value >= critical:
            return "CRITICAL"
        if value >= warning:
            return "WARNING"
        return "OK"

    # ============================================================
    # CPU METRICS
    # ============================================================

    def get_cpu_metrics(self) -> Dict[str, Any]:
        """
        Collect CPU metrics.

        Returns:
            Dictionary with CPU usage, core count, frequency, and status.
        """
        # interval=0.5 gives a more accurate reading than a snapshot
        usage_percent = psutil.cpu_percent(interval=0.5)
        per_core = psutil.cpu_percent(interval=0.0, percpu=True)

        # CPU frequency (may not be available on all systems)
        try:
            freq = psutil.cpu_freq()
            frequency_mhz = round(freq.current, 2) if freq else None
        except (NotImplementedError, AttributeError):
            frequency_mhz = None

        status = self._classify_status(
            usage_percent,
            self.CPU_WARNING_THRESHOLD,
            self.CPU_CRITICAL_THRESHOLD,
        )

        return {
            "usage_percent": usage_percent,
            "per_core_percent": per_core,
            "core_count_logical": psutil.cpu_count(logical=True),
            "core_count_physical": psutil.cpu_count(logical=False),
            "frequency_mhz": frequency_mhz,
            "status": status,
            "thresholds": {
                "warning": self.CPU_WARNING_THRESHOLD,
                "critical": self.CPU_CRITICAL_THRESHOLD,
            },
        }

    # ============================================================
    # MEMORY METRICS
    # ============================================================

    def get_memory_metrics(self) -> Dict[str, Any]:
        """
        Collect RAM and swap memory metrics.

        Returns:
            Dictionary with RAM and swap usage in bytes, GB, and percentage.
        """
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()

        status = self._classify_status(
            vm.percent,
            self.MEMORY_WARNING_THRESHOLD,
            self.MEMORY_CRITICAL_THRESHOLD,
        )

        return {
            "ram": {
                "total_gb": round(vm.total / (1024 ** 3), 2),
                "available_gb": round(vm.available / (1024 ** 3), 2),
                "used_gb": round(vm.used / (1024 ** 3), 2),
                "usage_percent": vm.percent,
            },
            "swap": {
                "total_gb": round(swap.total / (1024 ** 3), 2),
                "used_gb": round(swap.used / (1024 ** 3), 2),
                "usage_percent": swap.percent,
            },
            "status": status,
            "thresholds": {
                "warning": self.MEMORY_WARNING_THRESHOLD,
                "critical": self.MEMORY_CRITICAL_THRESHOLD,
            },
        }

    # ============================================================
    # DISK METRICS
    # ============================================================

    def get_disk_metrics(self) -> Dict[str, Any]:
        """
        Collect disk usage metrics for all mounted partitions.

        Returns:
            Dictionary with per-partition usage and overall status.
        """
        partitions_data = []
        worst_usage = 0.0

        for partition in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                partitions_data.append({
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "filesystem": partition.fstype,
                    "total_gb": round(usage.total / (1024 ** 3), 2),
                    "used_gb": round(usage.used / (1024 ** 3), 2),
                    "free_gb": round(usage.free / (1024 ** 3), 2),
                    "usage_percent": usage.percent,
                })
                worst_usage = max(worst_usage, usage.percent)
            except PermissionError:
                # Some partitions (e.g. CD-ROM) may not be accessible
                continue

        status = self._classify_status(
            worst_usage,
            self.DISK_WARNING_THRESHOLD,
            self.DISK_CRITICAL_THRESHOLD,
        )

        return {
            "partitions": partitions_data,
            "worst_usage_percent": worst_usage,
            "status": status,
            "thresholds": {
                "warning": self.DISK_WARNING_THRESHOLD,
                "critical": self.DISK_CRITICAL_THRESHOLD,
            },
        }

    # ============================================================
    # NETWORK METRICS
    # ============================================================

    def get_network_metrics(self) -> Dict[str, Any]:
        """
        Collect network I/O statistics.

        Returns:
            Dictionary with bytes sent/received and packet counts.
        """
        net = psutil.net_io_counters()

        return {
            "bytes_sent_mb": round(net.bytes_sent / (1024 ** 2), 2),
            "bytes_recv_mb": round(net.bytes_recv / (1024 ** 2), 2),
            "packets_sent": net.packets_sent,
            "packets_recv": net.packets_recv,
            "errors_in": net.errin,
            "errors_out": net.errout,
            "drops_in": net.dropin,
            "drops_out": net.dropout,
        }

    # ============================================================
    # COMPLETE SNAPSHOT
    # ============================================================

    def get_snapshot(self) -> Dict[str, Any]:
        """
        Get a complete snapshot of all system metrics.

        This is the main entry point for the monitoring API.
        Aggregates CPU, memory, disk, and network metrics in a single call.

        Returns:
            Dictionary with timestamp, hostname, and all metrics.
        """
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "hostname": self._hostname,
            "cpu": self.get_cpu_metrics(),
            "memory": self.get_memory_metrics(),
            "disk": self.get_disk_metrics(),
            "network": self.get_network_metrics(),
        }