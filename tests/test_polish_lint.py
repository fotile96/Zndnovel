"""tools/polish_lint.py 的行为闸。

每条用例钉的是一个**会被搞错的判断**，不是覆盖率。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import polish_lint as pl


def _lane(tmp_path, rows):
    """rows: [(id, jp, zh)]。"""
    d = tmp_path / "data"
    d.mkdir()
    (d / "ledger.jsonl").write_text(
        "\n".join(json.dumps({"id": i, "jp": j}, ensure_ascii=False) for i, j, _ in rows) + "\n",
        encoding="utf-8")
    (d / "forward.jsonl").write_text(
        "\n".join(json.dumps({"id": i, "zh": z}, ensure_ascii=False) for i, _, z in rows) + "\n",
        encoding="utf-8")
    return d


def test_s9b_needs_both_sides_to_match(tmp_path):
    """jp 是「Xと私」且 zh 仍是「X和我」才算——只满足一边的都是误报。"""
    d = _lane(tmp_path, [
        (1, "【彩野】「サクラさんと私、会ってたの」", "【彩野】「サクラ同学和我，见过面」"),   # 命中
        (2, "【彩野】「サクラさんと私、会ってたの」", "【彩野】「我和サクラ同学，见过面」"),   # 已改好
        (3, "サクラさんと彩野さんが会った。", "サクラ同学和我见过面。"),                    # jp 无「と私」
    ])
    hits = [h[0] for h in pl.lint(d, ["S9b-order"])["S9b-order"]]
    assert hits == [1]


def test_patches_override_forward(tmp_path):
    """清点必须看**车道现行**——已回改的行不该再报。"""
    d = _lane(tmp_path, [(1, "【彩野】「サクラさんと私、会ってたの」",
                          "【彩野】「サクラ同学和我，见过面」")])
    (d / "patches.jsonl").write_text(
        json.dumps({"id": 1, "zh": "【彩野】「我和サクラ同学，见过面」"}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    assert pl.lint(d, ["S9b-order"])["S9b-order"] == []


def test_tail_and_mid_are_different_buckets(tmp_path):
    """句末 `……。`（可机械删）与行中 `……。`（判断题）必须分开计数，不能混。"""
    d = _lane(tmp_path, [
        (1, "あ", "句末……。"),
        (2, "い", "行中……。还有后文"),
        (3, "う", "两者都有……。中间……。"),      # 行中 1 + 句末 1
    ])
    res = pl.lint(d, ["S7a-tail", "S7a-mid"])
    assert [h[0] for h in res["S7a-tail"]] == [1, 3]
    assert [h[0] for h in res["S7a-mid"]] == [2, 3]


def test_control_code_counts_as_line_end(tmp_path):
    """`_n`/`_r` 之前也是句末——引擎在那里换行，视觉上就是行尾。"""
    d = _lane(tmp_path, [(1, "あ", "上半……。_n下半")])
    assert [h[0] for h in pl.lint(d, ["S7a-tail"])["S7a-tail"]] == [1]
    assert pl.lint(d, ["S7a-mid"])["S7a-mid"] == []


def test_exit_code_is_zero_even_with_hits(tmp_path, capsys):
    """⚠ 台账不是闸：有命中也必须 rc=0，否则「待人裁」会被 CI 读成「构建失败」。"""
    d = _lane(tmp_path, [(1, "【彩野】「サクラさんと私」", "【彩野】「サクラ同学和我」")])
    assert pl.main(["--data-dir", str(d)]) == 0
    assert "S9b-order" in capsys.readouterr().out
