import json
from loop_engineering.output import Status, Result

def _r(**kw):
    base = dict(role="verify", status=Status.UNKNOWN, child_exit_code=0, exit_code=3,
                loop_status=None, started_at="2026-10-17T10:00:00+08:00",
                finished_at="2026-10-17T10:00:01+08:00", error=None,
                wrapper_path="/s/loop_auto_verify.sh", child_stdout="hi\n")
    base.update(kw); return Result(**base)

def test_to_dict_has_all_contract_fields():
    d = _r().to_dict()
    assert set(d) == {"role","status","child_exit_code","exit_code","loop_status",
                      "started_at","finished_at","error","wrapper_path","child_stdout"}
    assert d["status"] == "unknown"                       # Enum → str

def test_not_started_has_null_child_exit_code_and_error():
    d = _r(child_exit_code=None, exit_code=5, error="start failed").to_dict()
    assert d["child_exit_code"] is None and d["error"] == "start failed"

def test_serializes_to_single_json_object():
    assert json.loads(json.dumps(_r().to_dict()))["role"] == "verify"
