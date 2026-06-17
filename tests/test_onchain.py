"""Unit tests for the pure net-flow aggregation core (no network)."""

from signals.onchain import aggregate_net, _direction

W1 = "0x1111111111111111111111111111111111111111"
W2 = "0x2222222222222222222222222222222222222222"
OTHER = "0x9999999999999999999999999999999999999999"
SCALE = 10 ** 18


def _t(n):  # n tokens -> raw
    return int(n * SCALE)


def test_receiving_is_positive():
    # W1 receives 10 from an untracked address
    net, active = aggregate_net([(OTHER, W1, _t(10))], {W1}, SCALE)
    assert net == 10.0
    assert active == 1


def test_sending_is_negative():
    net, active = aggregate_net([(W1, OTHER, _t(4))], {W1}, SCALE)
    assert net == -4.0
    assert active == 1


def test_untracked_wallets_ignored():
    net, active = aggregate_net([(OTHER, OTHER, _t(100))], {W1, W2}, SCALE)
    assert net == 0.0
    assert active == 0


def test_nets_across_wallets():
    events = [
        (OTHER, W1, _t(10)),   # W1 +10
        (W1, OTHER, _t(3)),    # W1 -3  -> W1 net +7
        (OTHER, W2, _t(5)),    # W2 +5
    ]
    net, active = aggregate_net(events, {W1, W2}, SCALE)
    assert net == 12.0         # 7 + 5
    assert active == 2


def test_case_insensitive_addresses():
    net, _ = aggregate_net([(OTHER, W1.upper(), _t(2))], {W1}, SCALE)
    assert net == 2.0


def test_direction_thresholds():
    assert _direction(5.0) == "in"
    assert _direction(-5.0) == "out"
    assert _direction(0.0) == "flat"
