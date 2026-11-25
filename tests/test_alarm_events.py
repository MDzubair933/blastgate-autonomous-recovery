"""
BlastGate Alarm Event Validation Tests (T4-014, T4-015)
Tests EventBridge CloudWatch Alarm State Change event validation, account, region, and prefix boundaries.
"""

import pytest
from incidents.validator import AlarmEventValidator


@pytest.fixture
def valid_alarm_event():
    return {
        "version": "0",
        "id": "event-12345",
        "detail-type": "CloudWatch Alarm State Change",
        "source": "aws.cloudwatch",
        "account": "123456789012",
        "time": "2026-11-22T12:00:00Z",
        "region": "us-east-1",
        "resources": [
            "arn:aws:cloudwatch:us-east-1:123456789012:alarm:blastgate-worker-stalled-alarm"
        ],
        "detail": {
            "alarmName": "blastgate-worker-stalled-alarm",
            "state": {
                "value": "ALARM",
                "reason": "Threshold Breached: 1 datapoint [1.0] was greater than or equal to threshold [1.0]",
                "timestamp": "2026-11-22T12:00:00.000+0000"
            },
            "previousState": {
                "value": "OK",
                "reason": "Threshold Not Breached"
            },
            "configuration": {
                "metrics": [
                    {
                        "metricStat": {
                            "metric": {
                                "namespace": "BlastGate/Workers",
                                "name": "ConfirmedStalledWorkerCount"
                            }
                        }
                    }
                ]
            }
        }
    }


def test_valid_alarm_event_passes(valid_alarm_event):
    """T4-014: Valid CloudWatch Alarm state change passes all checks."""
    validator = AlarmEventValidator()
    result = validator.validate_event(valid_alarm_event)

    assert result["is_valid"] is True
    assert result["alarm_name"] == "blastgate-worker-stalled-alarm"
    assert result["new_state"] == "ALARM"


def test_invalid_alarm_name_prefix_rejected(valid_alarm_event):
    """T4-015: Alarm name without 'blastgate-' prefix is strictly rejected."""
    validator = AlarmEventValidator()
    valid_alarm_event["detail"]["alarmName"] = "unauthorized-prod-alarm"
    result = validator.validate_event(valid_alarm_event)

    assert result["is_valid"] is False
    assert "prefix" in result["error"].lower()


def test_wrong_aws_account_rejected(valid_alarm_event):
    """Event from unauthorized account is rejected."""
    validator = AlarmEventValidator(expected_account="123456789012")
    valid_alarm_event["account"] = "123456789012"
    result = validator.validate_event(valid_alarm_event)

    assert result["is_valid"] is False
    assert "account" in result["error"].lower()


def test_wrong_aws_region_rejected(valid_alarm_event):
    """Event from unauthorized region is rejected."""
    validator = AlarmEventValidator(expected_region="us-east-1")
    valid_alarm_event["region"] = "eu-west-1"
    result = validator.validate_event(valid_alarm_event)

    assert result["is_valid"] is False
    assert "region" in result["error"].lower()


def test_wrong_source_rejected(valid_alarm_event):
    """Event from source other than aws.cloudwatch is rejected."""
    validator = AlarmEventValidator()
    valid_alarm_event["source"] = "custom.monitoring"
    result = validator.validate_event(valid_alarm_event)

    assert result["is_valid"] is False
    assert "source" in result["error"].lower()
