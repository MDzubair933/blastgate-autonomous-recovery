"""
BlastGate Atomic Cooldown Budget Tests (Rule R4 & Invariant 2)
Verifies rolling 600-second cluster-wide throttling.
"""

import pytest
from broker.budget import CooldownManager, MockStateStoreProvider
from broker.errors import CooldownActiveError


def test_first_reservation_succeeds():
    store = MockStateStoreProvider()
    mgr = CooldownManager(state_provider=store, cooldown_window_seconds=600, current_time_fn=lambda: 1000.0)

    res = mgr.reserve_budget(cluster_id="blastgate-sandbox", incident_id="inc-ee79976c9380d5e3")
    assert res.cluster_id == "blastgate-sandbox"
    assert res.reserved_at == 1000.0
    assert res.expires_at == 1600.0


def test_immediate_second_reservation_rejected():
    store = MockStateStoreProvider()
    mgr = CooldownManager(state_provider=store, cooldown_window_seconds=600, current_time_fn=lambda: 1000.0)

    # First succeeds
    mgr.reserve_budget(cluster_id="blastgate-sandbox", incident_id="inc-ee79976c9380d5e3")

    # Second at t=1010s must be rejected
    mgr.current_time_fn = lambda: 1010.0
    with pytest.raises(CooldownActiveError) as exc:
        mgr.reserve_budget(cluster_id="blastgate-sandbox", incident_id="inc-33a7d3da476a32ac")
    assert "Global cooldown active" in str(exc.value)
    assert "590.0s remaining" in str(exc.value)


def test_new_incident_id_cannot_bypass_cooldown():
    store = MockStateStoreProvider()
    mgr = CooldownManager(state_provider=store, cooldown_window_seconds=600, current_time_fn=lambda: 1000.0)

    mgr.reserve_budget(cluster_id="blastgate-sandbox", incident_id="inc-alpha")

    # Attacker tries different incident ID at t=1100s
    mgr.current_time_fn = lambda: 1100.0
    with pytest.raises(CooldownActiveError):
        mgr.reserve_budget(cluster_id="blastgate-sandbox", incident_id="inc-beta-bypass")


def test_reservation_after_window_expires_succeeds():
    store = MockStateStoreProvider()
    mgr = CooldownManager(state_provider=store, cooldown_window_seconds=600, current_time_fn=lambda: 1000.0)

    mgr.reserve_budget(cluster_id="blastgate-sandbox", incident_id="inc-first")

    # t = 1601s (cooldown window expired)
    mgr.current_time_fn = lambda: 1601.0
    res2 = mgr.reserve_budget(cluster_id="blastgate-sandbox", incident_id="inc-second")
    assert res2.reserved_at == 1601.0
    assert res2.expires_at == 2201.0
