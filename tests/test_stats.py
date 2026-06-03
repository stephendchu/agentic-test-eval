"""Offline tests for the paired stats helpers."""

from atw.metrics.stats import paired_bootstrap, wilson_ci


def test_paired_bootstrap_clear_positive_excludes_zero():
    r = paired_bootstrap([8, 10, 12, 9, 11, 10], seed=0)
    assert r["mean_diff"] > 0
    assert r["excludes_zero"] is True
    assert r["ci_low"] > 0


def test_paired_bootstrap_noise_includes_zero():
    r = paired_bootstrap([-5, 6, -4, 5, -6, 4], seed=0)
    assert r["excludes_zero"] is False


def test_paired_bootstrap_empty():
    assert paired_bootstrap([])["n"] == 0


def test_wilson_ci_strong_preference():
    r = wilson_ci(wins=9, n=10)
    assert r["win_rate"] == 0.9
    assert r["excludes_half"] is True


def test_wilson_ci_coinflip_includes_half():
    r = wilson_ci(wins=5, n=10)
    assert r["excludes_half"] is False
