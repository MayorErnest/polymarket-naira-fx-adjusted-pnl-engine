import pytest

from calc import Flow, FlowError, calculate


def test_readme_example():
    r = calculate([Flow("deposit", 100, 150_000), Flow("withdrawal", 120, 165_000)])
    assert r.usd_profit == 20
    assert r.real_profit_ngn == 15_000
    assert r.avg_deposit_rate == 1_500
    assert r.fx_effect_ngn == -15_000  # 120 x (1,375 - 1,500)
    assert r.tax_ngn == 1_500


def test_average_rate_is_weighted_by_size():
    r = calculate([Flow("deposit", 10, 15_000), Flow("deposit", 1_000, 1_600_000)])
    assert r.avg_deposit_rate == pytest.approx(1_615_000 / 1_010)


def test_kind_is_case_insensitive():
    r = calculate([Flow("Deposit", 100, 150_000), Flow(" WITHDRAWAL ", 120, 165_000)])
    assert r.real_profit_ngn == 15_000


def test_unknown_kind_is_rejected_not_ignored():
    with pytest.raises(FlowError, match="Row 2"):
        calculate([Flow("deposit", 100, 150_000), Flow("withdraw", 120, 165_000)])


def test_missing_naira_is_rejected_not_zero():
    with pytest.raises(FlowError, match="Row 1: enter the naira you paid"):
        calculate([Flow("deposit", 100, None)])


def test_zero_naira_is_rejected():
    with pytest.raises(FlowError):
        calculate([Flow("withdrawal", 50, 0)])


def test_money_still_inside():
    # Deposited, nothing withdrawn, $130 still inside, sell rate today 1,450.
    r = calculate([Flow("deposit", 100, 150_000)], usd_inside=130, today_rate=1_450)
    assert r.real_profit_ngn == -150_000  # cashed-out view
    assert r.total_profit_ngn == 38_500  # 130 x 1,450 - 150,000


def test_total_is_none_without_both_inputs():
    r = calculate([Flow("deposit", 100, 150_000)], usd_inside=130)
    assert r.total_profit_ngn is None


def test_no_deposits_leaves_fx_blank():
    r = calculate([Flow("withdrawal", 50, 70_000)])
    assert r.avg_deposit_rate is None
    assert r.fx_effect_ngn is None


def test_loss_owes_no_tax():
    r = calculate([Flow("deposit", 100, 150_000), Flow("withdrawal", 80, 110_000)])
    assert r.tax_ngn == 0