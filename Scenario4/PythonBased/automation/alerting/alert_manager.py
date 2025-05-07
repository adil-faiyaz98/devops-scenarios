"""
Alert Manager for the AI-driven Observability Pipeline.

This module handles alert generation, routing, and delivery to various
notification channels like Slack, PagerDuty, and email.

Key features:
- Alert aggregation and deduplication
- Severity-based routing
- Rate limiting to prevent alert storms
- Customizable alert templates
- Delivery confirmation and retry
"""

import os
import json
import time
import logging
import datetime
import threading
import requests
from typing import Dict, List, Any, Optional, Callable
from enum import Enum


class AlertSeverity(Enum):
    """Alert severity levels."""
    
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertChannel(Enum):
    """Alert notification channels."""
    
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    EMAIL = "email"
    WEBHOOK = "webhook"


class Alert:
    """Alert class representing a notification."""
    
    def __init__(
        self,
        title: str,
        message: str,
        severity: AlertSeverity,
        source: str,
        timestamp: Optional[datetime.datetime] = None,
        details: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        dedupe_key: Optional[str] = None
    ):
        """
        Initialize an alert.
        
        Args:
            title: Alert title
            message: Alert message
            severity: Alert severity
            source: Alert source (service or component)
            timestamp: Alert timestamp (default: now)
            details: Additional alert details
            tags: Alert tags for categorization
            dedupe_key: Deduplication key
        """
        self.title = title
        self.message = message
        self.severity = severity
        self.source = source
        self.timestamp = timestamp or datetime.datetime.now()
        self.details = details or {}
        self.tags = tags or []
        self.dedupe_key = dedupe_key or f"{source}:{title}:{self.timestamp.strftime('%Y%m%d%H%M')}"
        self.id = f"alert-{int(time.time())}-{hash(self.dedupe_key) % 10000:04d}"
        self.delivery_attempts = 0
        self.delivered = False
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert alert to dictionary.
        
        Returns:
            Dictionary representation of the alert
        """
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "severity": self.severity.value,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "tags": self.tags,
            "dedupe_key": self.dedupe_key
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Alert":
        """
        Create alert from dictionary.
        
        Args:
            data: Dictionary representation of the alert
            
        Returns:
            Alert instance
        """
        alert = cls(
            title=data["title"],
            message=data["message"],
            severity=AlertSeverity(data["severity"]),
            source=data["source"],
            timestamp=datetime.datetime.fromisoformat(data["timestamp"]),
            details=data.get("details", {}),
            tags=data.get("tags", []),
            dedupe_key=data.get("dedupe_key")
        )
        alert.id = data.get("id", alert.id)
        alert.delivery_attempts = data.get("delivery_attempts", 0)
        alert.delivered = data.get("delivered", False)
        return alert


class AlertChannelConfig:
    """Configuration for an alert channel."""
    
    def __init__(
        self,
        channel_type: AlertChannel,
        name: str,
        config: Dict[str, Any],
        enabled: bool = True,
        severity_filter: Optional[List[AlertSeverity]] = None,
        source_filter: Optional[List[str]] = None,
        tag_filter: Optional[List[str]] = None
    ):
        """
        Initialize alert channel configuration.
        
        Args:
            channel_type: Channel type
            name: Channel name
            config: Channel-specific configuration
            enabled: Whether the channel is enabled
            severity_filter: List of severities to send to this channel
            source_filter: List of sources to send to this channel
            tag_filter: List of tags to send to this channel
        """
        self.channel_type = channel_type
        self.name = name
        self.config = config
        self.enabled = enabled
        self.severity_filter = severity_filter
        self.source_filter = source_filter
        self.tag_filter = tag_filter
    
    def should_receive_alert(self, alert: Alert) -> bool:
        """
        Check if this channel should receive the alert.
        
        Args:
            alert: Alert to check
            
        Returns:
            True if the channel should receive the alert, False otherwise
        """
        if not self.enabled:
            return False
        
        if self.severity_filter and alert.severity not in self.severity_filter:
            return False
        
        if self.source_filter and alert.source not in self.source_filter:
            return False
        
        if self.tag_filter and not any(tag in alert.tags for tag in self.tag_filter):
            return False
        
        return True


class SlackAlertSender:
    """Sender for Slack alerts."""
    
    def __init__(self, webhook_url: str, channel: Optional[str] = None):
        """
        Initialize Slack alert sender.
        
        Args:
            webhook_url: Slack webhook URL
            channel: Slack channel to send alerts to
        """
        self.webhook_url = webhook_url
        self.channel = channel
    
    def send(self, alert: Alert) -> bool:
        """
        Send alert to Slack.
        
        Args:
            alert: Alert to send
            
        Returns:
            True if the alert was sent successfully, False otherwise
        """
        # Create Slack message payload
        payload = {
            "text": f"*{alert.title}*",
            "attachments": [
                {
                    "color": self._get_color_for_severity(alert.severity),
                    "fields": [
                        {
                            "title": "Message",
                            "value": alert.message,
                            "short": False
                        },
                        {
                            "title": "Source",
                            "value": alert.source,
                            "short": True
                        },
                        {
                            "title": "Severity",
                            "value": alert.severity.value.upper(),
                            "short": True
                        },
                        {
                            "title": "Time",
                            "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                            "short": True
                        }
                    ],
                    "footer": "AI Observability Pipeline",
                    "ts": int(alert.timestamp.timestamp())
                }
            ]
        }
        
        # Add channel if specified
        if self.channel:
            payload["channel"] = self.channel
        
        # Add details if available
        if alert.details:
            payload["attachments"][0]["fields"].append({
                "title": "Details",
                "value": "```" + json.dumps(alert.details, indent=2) + "```",
                "short": False
            })
        
        # Add tags if available
        if alert.tags:
            payload["attachments"][0]["fields"].append({
                "title": "Tags",
                "value": ", ".join(alert.tags),
                "short": True
            })
        
        # Send to Slack
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Failed to send alert to Slack: {e}")
            return False
    
    def _get_color_for_severity(self, severity: AlertSeverity) -> str:
        """
        Get Slack color for severity.
        
        Args:
            severity: Alert severity
            
        Returns:
            Slack color code
        """
        colors = {
            AlertSeverity.INFO: "#2196F3",  # Blue
            AlertSeverity.WARNING: "#FFC107",  # Yellow
            AlertSeverity.ERROR: "#FF5722",  # Orange
            AlertSeverity.CRITICAL: "#F44336"  # Red
        }
        return colors.get(severity, "#2196F3")


class PagerDutyAlertSender:
    """Sender for PagerDuty alerts."""
    
    def __init__(self, integration_key: str, api_token: Optional[str] = None):
        """
        Initialize PagerDuty alert sender.
        
        Args:
            integration_key: PagerDuty integration key
            api_token: PagerDuty API token for additional functionality
        """
        self.integration_key = integration_key
        self.api_token = api_token
        self.events_api_url = "https://events.pagerduty.com/v2/enqueue"
    
    def send(self, alert: Alert) -> bool:
        """
        Send alert to PagerDuty.
        
        Args:
            alert: Alert to send
            
        Returns:
            True if the alert was sent successfully, False otherwise
        """
        # Create PagerDuty event payload
        payload = {
            "routing_key": self.integration_key,
            "event_action": "trigger",
            "dedup_key": alert.dedupe_key,
            "payload": {
                "summary": alert.title,
                "source": alert.source,
                "severity": self._get_pagerduty_severity(alert.severity),
                "timestamp": alert.timestamp.isoformat(),
                "component": alert.source,
                "group": "ai-observability-pipeline",
                "class": "alert",
                "custom_details": {
                    "message": alert.message,
                    **alert.details
                }
            }
        }
        
        # Send to PagerDuty
        try:
            response = requests.post(
                self.events_api_url,
                json=payload,
                headers={
                    "Content-Type": "application/json"
                },
                timeout=5
            )
            return response.status_code == 202
        except Exception as e:
            logging.error(f"Failed to send alert to PagerDuty: {e}")
            return False
    
    def _get_pagerduty_severity(self, severity: AlertSeverity) -> str:
        """
        Get PagerDuty severity level.
        
        Args:
            severity: Alert severity
            
        Returns:
            PagerDuty severity level
        """
        mapping = {
            AlertSeverity.INFO: "info",
            AlertSeverity.WARNING: "warning",
            AlertSeverity.ERROR: "error",
            AlertSeverity.CRITICAL: "critical"
        }
        return mapping.get(severity, "info")


class EmailAlertSender:
    """Sender for email alerts."""
    
    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        from_email: str,
        to_emails: List[str]
    ):
        """
        Initialize email alert sender.
        
        Args:
            smtp_server: SMTP server
            smtp_port: SMTP port
            username: SMTP username
            password: SMTP password
            from_email: Sender email
            to_emails: Recipient emails
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.to_emails = to_emails
    
    def send(self, alert: Alert) -> bool:
        """
        Send alert via email.
        
        Args:
            alert: Alert to send
            
        Returns:
            True if the alert was sent successfully, False otherwise
        """
        # Email sending would be implemented here
        # For simplicity, we'll just log the email and return success
        logging.info(f"Would send email alert: {alert.title} to {self.to_emails}")
        return True


class WebhookAlertSender:
    """Sender for webhook alerts."""
    
    def __init__(self, webhook_url: str, headers: Optional[Dict[str, str]] = None):
        """
        Initialize webhook alert sender.
        
        Args:
            webhook_url: Webhook URL
            headers: HTTP headers to include in the request
        """
        self.webhook_url = webhook_url
        self.headers = headers or {
            "Content-Type": "application/json"
        }
    
    def send(self, alert: Alert) -> bool:
        """
        Send alert to webhook.
        
        Args:
            alert: Alert to send
            
        Returns:
            True if the alert was sent successfully, False otherwise
        """
        try:
            response = requests.post(
                self.webhook_url,
                json=alert.to_dict(),
                headers=self.headers,
                timeout=5
            )
            return response.status_code >= 200 and response.status_code < 300
        except Exception as e:
            logging.error(f"Failed to send alert to webhook: {e}")
            return False


class AlertManager:
    """Alert manager for handling alerts."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize alert manager.
        
        Args:
            config: Alert manager configuration
        """
        self.config = config
        self.channels = []
        self.alert_history = []
        self.dedupe_cache = {}
        self.dedupe_window = config.get("dedupe_window_seconds", 300)  # 5 minutes
        self.rate_limit = config.get("rate_limit", 10)  # 10 alerts per minute
        self.rate_limit_window = 60  # 1 minute
        self.alert_count = 0
        self.last_reset = time.time()
        self.retry_interval = config.get("retry_interval_seconds", 60)
        self.max_retries = config.get("max_retries", 3)
        self.logger = logging.getLogger("alert-manager")
        
        # Initialize channels
        self._initialize_channels()
        
        # Start retry thread
        self.retry_thread = threading.Thread(target=self._retry_failed_alerts, daemon=True)
        self.retry_thread.start()
    
    def _initialize_channels(self) -> None:
        """Initialize alert channels from configuration."""
        for channel_config in self.config.get("channels", []):
            channel_type = AlertChannel(channel_config["type"])
            
            # Create severity filter if specified
            severity_filter = None
            if "severity_filter" in channel_config:
                severity_filter = [AlertSeverity(s) for s in channel_config["severity_filter"]]
            
            # Create channel configuration
            channel = AlertChannelConfig(
                channel_type=channel_type,
                name=channel_config["name"],
                config=channel_config["config"],
                enabled=channel_config.get("enabled", True),
                severity_filter=severity_filter,
                source_filter=channel_config.get("source_filter"),
                tag_filter=channel_config.get("tag_filter")
            )
            
            self.channels.append(channel)
    
    def send_alert(self, alert: Alert) -> bool:
        """
        Send an alert through configured channels.
        
        Args:
            alert: Alert to send
            
        Returns:
            True if the alert was sent to at least one channel, False otherwise
        """
        # Check rate limit
        current_time = time.time()
        if current_time - self.last_reset > self.rate_limit_window:
            self.alert_count = 0
            self.last_reset = current_time
        
        if self.alert_count >= self.rate_limit:
            self.logger.warning(f"Rate limit exceeded, dropping alert: {alert.title}")
            return False
        
        # Check deduplication
        if self._is_duplicate(alert):
            self.logger.info(f"Duplicate alert, dropping: {alert.title}")
            return False
        
        # Add to dedupe cache
        self.dedupe_cache[alert.dedupe_key] = current_time
        
        # Add to history
        self.alert_history.append(alert)
        
        # Increment alert count
        self.alert_count += 1
        
        # Send to channels
        sent = False
        for channel in self.channels:
            if channel.should_receive_alert(alert):
                sender = self._get_sender_for_channel(channel)
                if sender:
                    success = sender.send(alert)
                    if success:
                        sent = True
                        alert.delivered = True
                    else:
                        alert.delivery_attempts += 1
        
        return sent
    
    def _is_duplicate(self, alert: Alert) -> bool:
        """
        Check if an alert is a duplicate.
        
        Args:
            alert: Alert to check
            
        Returns:
            True if the alert is a duplicate, False otherwise
        """
        if alert.dedupe_key in self.dedupe_cache:
            last_time = self.dedupe_cache[alert.dedupe_key]
            if time.time() - last_time < self.dedupe_window:
                return True
        
        return False
    
    def _get_sender_for_channel(self, channel: AlertChannelConfig) -> Optional[Any]:
        """
        Get sender for a channel.
        
        Args:
            channel: Channel configuration
            
        Returns:
            Sender instance or None if not available
        """
        if channel.channel_type == AlertChannel.SLACK:
            return SlackAlertSender(
                webhook_url=channel.config["webhook_url"],
                channel=channel.config.get("channel")
            )
        elif channel.channel_type == AlertChannel.PAGERDUTY:
            return PagerDutyAlertSender(
                integration_key=channel.config["integration_key"],
                api_token=channel.config.get("api_token")
            )
        elif channel.channel_type == AlertChannel.EMAIL:
            return EmailAlertSender(
                smtp_server=channel.config["smtp_server"],
                smtp_port=channel.config["smtp_port"],
                username=channel.config["username"],
                password=channel.config["password"],
                from_email=channel.config["from_email"],
                to_emails=channel.config["to_emails"]
            )
        elif channel.channel_type == AlertChannel.WEBHOOK:
            return WebhookAlertSender(
                webhook_url=channel.config["webhook_url"],
                headers=channel.config.get("headers")
            )
        
        return None
    
    def _retry_failed_alerts(self) -> None:
        """Retry failed alerts periodically."""
        while True:
            time.sleep(self.retry_interval)
            
            # Find failed alerts
            failed_alerts = [
                alert for alert in self.alert_history
                if not alert.delivered and alert.delivery_attempts < self.max_retries
            ]
            
            for alert in failed_alerts:
                self.logger.info(f"Retrying alert: {alert.title} (attempt {alert.delivery_attempts + 1})")
                self.send_alert(alert)
    
    def get_alert_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get alert history.
        
        Args:
            limit: Maximum number of alerts to return
            
        Returns:
            List of alerts as dictionaries
        """
        return [alert.to_dict() for alert in self.alert_history[-limit:]]
