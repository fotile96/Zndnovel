from tools.resolve import resolve_map

FWD = [{"id": 1, "zh": "初译A"}, {"id": 2, "zh": "初译B"}, {"id": 1, "zh": "二遍A"}]
PATCH = [{"id": 2, "zh": "补丁B1"}, {"id": 2, "zh": "补丁B2"}]

def test_forward_last_wins():
    assert resolve_map(FWD, [])[1] == "二遍A"

def test_patch_overrides_forward_and_last_patch_wins():
    m = resolve_map(FWD, PATCH)
    assert m[2] == "补丁B2"
    assert m[1] == "二遍A"

def test_untranslated_absent():
    assert 99 not in resolve_map(FWD, PATCH)
