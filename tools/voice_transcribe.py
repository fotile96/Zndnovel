"""语音素材转写：DATA.BIN 的 voice/<ID>.at3 → wav（ffmpeg）→ 日文文本（mlx-whisper，本机推理，不出网）。

用途：核对「字与声不一致」的演出——e2f 4838– 那组 `【≦ユウイチ≧】≪…≫` 对白的配音是
NAO（直哉）而不是 YUI，且念的词与字幕有出入；本工具把配音实际念的内容转写下来留档，
并按同一口径扫其它可疑行（说话人标签与语音前缀不一致的行，见 docs/ops 台账）。

用法（临时覆盖环境装 mlx-whisper，不动项目 venv）：
    uv run --with mlx-whisper python tools/voice_transcribe.py --ids 4815-4858,16753-16794 \
        --out build/voice_asr.jsonl
    --prime   第二遍：把该行字幕（剥掉标记）当 initial_prompt 喂给模型。被字幕"带着走"
              之后仍偏离的地方，才是硬证据；不带 prompt 的第一遍用来看模型自己听到了什么。
    --model   默认 mlx-community/whisper-large-v3-turbo（首跑从 HF 下载约 1.6 GB）。

前提：build/databin/ 已由 `tools/databin.py unpack assets/DATA.BIN build/databin` 展开；ffmpeg 在 PATH。
输出每行：{id, voice, file, func, jp, jp_plain, asr, prime, model, dur_s}。
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO, read_jsonl  # noqa: E402

VOICE_DIR = REPO / "build" / "databin" / "voice"
WAV_DIR = REPO / "build" / "voice_wav"
DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"

_LABEL = re.compile(r"^【[^】]*】")
_RUBY = re.compile(r"<([^,>]+),[^>]+>")


def plain(jp: str) -> str:
    """剥掉说话人标签、引号壳、控制码与 ruby，只留念白本身。"""
    s = _LABEL.sub("", jp)
    s = _RUBY.sub(r"\1", s)
    s = s.replace("_n", "").replace("_r", "")
    return re.sub(r"[≪≫≦≧「」『』]", "", s).strip()


def parse_ids(spec: str) -> set:
    out = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


def decode(voice: str) -> Path:
    src = VOICE_DIR / f"{voice}.at3"
    dst = WAV_DIR / f"{voice}.wav"
    if not src.exists():
        raise FileNotFoundError(src)
    if not dst.exists():
        WAV_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
                        "-ar", "16000", "-ac", "1", str(dst)], check=True)
    return dst


def duration(wav: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(wav)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ids", required=True, help="vms id 集合，如 4815-4858,16753,16755")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--prime", action="store_true", help="用字幕原文做 initial_prompt")
    args = ap.parse_args(argv)

    import mlx_whisper  # 延迟导入：只有真跑转写才需要

    want = parse_ids(args.ids)
    rows = [r for r in read_jsonl(REPO / "data" / "ledger.jsonl")
            if r["id"] in want and r["voice"] not in ("NONVOICE", "NORECORD")]
    rows.sort(key=lambda r: r["id"])
    print(f"[voice_transcribe] {len(rows)} 条有声行，模型 {args.model}，prime={args.prime}", file=sys.stderr)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for r in rows:
            wav = decode(r["voice"])
            jp_plain = plain(r["jp"])
            kw = dict(path_or_hf_repo=args.model, language="ja", temperature=0.0,
                      condition_on_previous_text=False)
            if args.prime:
                kw["initial_prompt"] = jp_plain
            res = mlx_whisper.transcribe(str(wav), **kw)
            asr = res["text"].strip()
            rec = {"id": r["id"], "voice": r["voice"], "file": r["file"], "func": r["func"],
                   "jp": r["jp"], "jp_plain": jp_plain, "asr": asr, "prime": args.prime,
                   "model": args.model, "dur_s": round(duration(wav), 2)}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            flag = "  " if asr.replace(" ", "") == jp_plain.replace(" ", "") else "≠ "
            print(f"{flag}[{r['id']}] {r['voice']} ({rec['dur_s']}s)\n    字：{jp_plain}\n    声：{asr}", file=sys.stderr)
    print(f"[voice_transcribe] 写入 {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
