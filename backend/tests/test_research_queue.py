import backend.db as db_module
from backend.db import init_db
from backend.routers.research_queue import list_research_queue, patch_research_queue_item, upsert_research_queue
from backend.schemas import ResearchQueuePatchRequest, ResearchQueueRequest


def _use_temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    init_db()


def test_research_queue_upsert_and_status_patch(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)

    created = upsert_research_queue(
        ResearchQueueRequest(
            ticker="MSFT",
            name="Microsoft Corp",
            status="candidate",
            tags=["AI", "云计算"],
            entry_reason="发现雷达提示值得初筛。",
            priority_score=88,
            discovery_label="重点研究",
        )
    )

    assert created["ticker"] == "MSFT"
    assert created["status"] == "candidate"
    assert created["tags"] == ["AI", "云计算"]

    updated = patch_research_queue_item("MSFT", ResearchQueuePatchRequest(status="deep_research"))

    assert updated["status_label"] == "深度研究中"
    assert list_research_queue()[0]["ticker"] == "MSFT"
