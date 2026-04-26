from backend.routers.companies import _peer_summary


def test_peer_summary_labels_current_more_expensive_than_peer_average():
    current = {
        "ticker": "TEST",
        "status": "ready",
        "price_to_fair": 1.4,
        "quality_score": 85,
    }
    peers = [
        {"ticker": "A", "status": "ready", "price_to_fair": 1.0, "quality_score": 80, "fcf_yield": 0.04},
        {"ticker": "B", "status": "ready", "price_to_fair": 1.1, "quality_score": 82, "fcf_yield": 0.03},
    ]

    summary = _peer_summary(current, peers)

    assert summary["relative_label"] == "比同行更贵"
    assert summary["available_count"] == 2


def test_peer_summary_handles_missing_peer_data():
    current = {
        "ticker": "TEST",
        "status": "ready",
        "price_to_fair": 1.0,
        "quality_score": 80,
    }

    summary = _peer_summary(current, [{"ticker": "A", "status": "missing_facts"}])

    assert summary["available_count"] == 0
    assert "还没有可比较数据" in summary["headline"]
