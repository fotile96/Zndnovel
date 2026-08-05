from tools.resolve import resolve_map, main
from tools.pipelib import write_jsonl, read_jsonl

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

def test_main_sorts_mixed_int_and_str_ids_without_typeerror(tmp_path, monkeypatch):
    """Important 5：计划规定 extra 车道的 id 是 str（如 "snr_x:1"），main/ambient
    车道是 int；合并后的 map 混有两种类型时，裸 sorted(m) 在 Python 3 下跨类型
    比较必抛 TypeError（sorted({1:'a','snr_x:5':'b'}) 已实测复现）。这一步是
    唯一能把 forward 产出注入 final.jsonl 的地方，任何一个 extra 车道批次入了
    forward，--require-complete 就会在这里死。改法：sorted(m, key=lambda k:
    (isinstance(k, str), k))——int 在前、str 在后，各自内部有序。去掉这个
    key= 参数（改回裸 sorted(m)）本测试必红（TypeError → 非 0 退出码）。"""
    write_jsonl(tmp_path / "ledger.jsonl",
                [{"id": 1, "jp": "a"}, {"id": "snr_x:1", "jp": "b"}])
    write_jsonl(tmp_path / "forward.jsonl",
                [{"id": 1, "zh": "译1"}, {"id": "snr_x:1", "zh": "译x1"}])
    monkeypatch.setattr("tools.resolve.DATA", tmp_path)
    assert main([]) == 0
    final = read_jsonl(tmp_path / "final.jsonl")
    assert [r["id"] for r in final] == [1, "snr_x:1"]     # int 在前、str 在后


def test_resolve_announces_when_forward_is_absent(tmp_path, capsys, monkeypatch):
    """漏传 --data-dir 时，`final=0` 与「这条线还没开译」在数字上完全一样。

    人眼分辨不出的失效必须出声——SEG-6 裁决会话实测踩到：读了仓库根 data/
    （有 ledger、无 forward），算出一张完全合理的空表并把空 final.jsonl 写进仓库根。
    """
    from tools.resolve import main
    d = tmp_path / "data"
    d.mkdir()
    (d / "ledger.jsonl").write_text('{"id":1,"jp":"あ"}\n', encoding="utf-8")
    assert main(["--data-dir", str(d)]) == 0
    err = capsys.readouterr().err
    assert "forward.jsonl 不存在" in err and "漏传" in err, err
    assert "final=0" in err


def test_resolve_data_dir_overrides_env_and_writes_there(tmp_path, capsys):
    """--data-dir 必须真的生效：读它、也写它，不能回落到仓库根。"""
    from tools.resolve import main
    d = tmp_path / "data"
    d.mkdir()
    (d / "ledger.jsonl").write_text('{"id":1,"jp":"あ"}\n', encoding="utf-8")
    (d / "forward.jsonl").write_text('{"id":1,"zh":"啊"}\n', encoding="utf-8")
    assert main(["--data-dir", str(d)]) == 0
    assert (d / "final.jsonl").exists(), "final.jsonl 须写在 --data-dir 里"
    err = capsys.readouterr().err
    assert "final=1" in err and "forward.jsonl 不存在" not in err
