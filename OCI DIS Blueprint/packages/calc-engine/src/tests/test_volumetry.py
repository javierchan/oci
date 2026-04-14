"""
Parity tests for the volumetry engine.

These tests establish the benchmark expectations from the workbook
and must pass before any Milestone is considered done (PRD-050, PRD-052).

Run with: pytest packages/calc-engine/src/tests/test_volumetry.py -v
"""
import pytest
from ..engine.volumetry import (
    Assumptions,
    IntegrationInput,
    executions_per_day,
    payload_per_hour_kb,
    oic_billing_messages_per_execution,
    oic_billing_messages_per_month,
    oic_peak_packs_per_hour,
    functions_invocations_per_month,
    functions_execution_units,
)

DEFAULTS = Assumptions()


# ---------------------------------------------------------------------------
# Frequency mapping
# ---------------------------------------------------------------------------

def test_frequency_diario():
    r = executions_per_day("Una vez al día")
    assert r.value == 1.0
    assert r.unit == "executions/day"


def test_frequency_hourly():
    r = executions_per_day("Cada hora")
    assert r.value == 24.0


def test_frequency_unknown():
    r = executions_per_day("Every quarter")
    assert r.value is None
    assert r.reason is not None


# ---------------------------------------------------------------------------
# OIC billing messages (50 KB threshold)
# ---------------------------------------------------------------------------

def test_oic_msgs_per_exec_single_chunk():
    # 30 KB payload + 10 KB response = 1 + 1 = 2 msgs
    r = oic_billing_messages_per_execution(30.0, 10.0, DEFAULTS)
    assert r.value == 2.0


def test_oic_msgs_per_exec_multi_chunk():
    # 110 KB payload → 3 msgs (50+50+10), 60 KB response → 2 msgs (50+10) = 5
    r = oic_billing_messages_per_execution(110.0, 60.0, DEFAULTS)
    assert r.value == 5.0


def test_oic_msgs_per_exec_exact_boundary():
    # Exactly 50 KB → 1 msg each
    r = oic_billing_messages_per_execution(50.0, 50.0, DEFAULTS)
    assert r.value == 2.0


def test_oic_msgs_per_month_daily():
    # 100 KB payload, 0 response, 1 exec/day, 30 days
    # msgs/exec = ceil(100/50) + 0 = 2
    # msgs/month = 2 * 1 * 30 = 60
    r = oic_billing_messages_per_month(100.0, 0.0, 1.0, DEFAULTS)
    assert r.value == 60.0


# ---------------------------------------------------------------------------
# OIC peak packs
# ---------------------------------------------------------------------------

def test_oic_peak_packs_exact():
    # 10000 peak msgs/hour → 2 packs
    r = oic_peak_packs_per_hour(10000.0, DEFAULTS)
    assert r.value == 2.0


def test_oic_peak_packs_rounds_up():
    # 5001 msgs → 2 packs (not 1)
    r = oic_peak_packs_per_hour(5001.0, DEFAULTS)
    assert r.value == 2.0


def test_oic_peak_packs_below_one_pack():
    r = oic_peak_packs_per_hour(100.0, DEFAULTS)
    assert r.value == 1.0


# ---------------------------------------------------------------------------
# Payload per hour
# ---------------------------------------------------------------------------

def test_payload_per_hour():
    # 100 KB/exec, 24 execs/day → 100 KB/hour
    r = payload_per_hour_kb(100.0, 24.0)
    assert r.value == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def test_functions_invocations_from_frequency():
    row = IntegrationInput(
        integration_id="test-01",
        payload_per_execution_kb=50.0,
        executions_per_day=4.0,
        trigger_type="Scheduled",
        is_real_time=False,
        core_tools="OIC Gen3, Functions",
        response_size_kb=0.0,
        is_fan_out=False,
        fan_out_targets=None,
    )
    r = functions_invocations_per_month(row, DEFAULTS)
    assert r.value == pytest.approx(4.0 * 30)


def test_functions_invocations_override():
    row = IntegrationInput(
        integration_id="test-02",
        payload_per_execution_kb=50.0,
        executions_per_day=4.0,
        trigger_type="Scheduled",
        is_real_time=False,
        core_tools="Functions",
        response_size_kb=0.0,
        is_fan_out=False,
        fan_out_targets=None,
        override_invocations_per_month=999.0,
    )
    r = functions_invocations_per_month(row, DEFAULTS)
    assert r.value == 999.0


def test_functions_execution_units():
    # 1000 invocations, 200ms, 256MB, 1 concurrency
    # = 1000 * 0.2 * 0.25 * 1 = 50 GB-s
    r = functions_execution_units(1000, 200, 256, 1)
    assert r.value == pytest.approx(50.0)
