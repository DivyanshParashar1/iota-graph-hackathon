import pytest

from ripple.ingest.dataco import order_frame, read_raw
from ripple.tools.impact import late_risk_baseline


@pytest.mark.parametrize("mode,market", [("Standard Class", "Europe"), ("First Class", "LATAM"),
                                         ("Second Class", "Pacific Asia")])
def test_late_risk_equals_pandas(scope_dataco, sample_ids, mode, market):
    raw = read_raw()
    o = order_frame(raw[raw["Order Id"].isin(set(sample_ids))])
    sel = o[(o["shipping_mode"] == mode) & (o["market"] == market)]
    r = late_risk_baseline(scope_dataco, mode=mode, market=market)
    assert r.data["sample"] == len(sel) > 0
    assert r.data["late_rate"] == pytest.approx(float(sel["late_risk"].mean()), abs=1e-9)
