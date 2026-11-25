"""
BlastGate EventBridge Alarm Event Validator
Validates structure, account, region, and approved alarm name.
"""

from typing import Dict, Any


class AlarmEventValidator:
    """Validates EventBridge CloudWatch Alarm state-change events."""

    def __init__(
        self,
        expected_account: str = "123456789012",
        expected_region: str = "us-east-1",
        expected_alarm_prefix: str = "blastgate-",
    ):
        self.expected_account = expected_account
        self.expected_region = expected_region
        self.expected_alarm_prefix = expected_alarm_prefix

    def validate_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates event envelope:
        - source == "aws.cloudwatch"
        - detail-type == "CloudWatch Alarm State Change"
        - account matches expected
        - region matches expected
        - alarm name starts with expected prefix
        """
        source = event.get("source")
        detail_type = event.get("detail-type")
        account = event.get("account")
        region = event.get("region")
        detail = event.get("detail", {})
        alarm_name = detail.get("alarmName", "")

        if source != "aws.cloudwatch":
            return {"is_valid": False, "error": f"Invalid event source '{source}', expected 'aws.cloudwatch'"}

        if detail_type != "CloudWatch Alarm State Change":
            return {"is_valid": False, "error": f"Invalid detail-type '{detail_type}'"}

        if account != self.expected_account:
            return {"is_valid": False, "error": f"Account mismatch '{account}' != '{self.expected_account}'"}

        if region != self.expected_region:
            return {"is_valid": False, "error": f"Region mismatch '{region}' != '{self.expected_region}'"}

        if not alarm_name.startswith(self.expected_alarm_prefix):
            return {"is_valid": False, "error": f"Alarm name '{alarm_name}' does not start with prefix '{self.expected_alarm_prefix}'"}

        new_state = detail.get("state", {}).get("value", "UNKNOWN")

        return {
            "is_valid": True,
            "alarm_name": alarm_name,
            "new_state": new_state,
            "timestamp": detail.get("state", {}).get("timestamp"),
            "configuration": detail.get("configuration", {}),
        }
