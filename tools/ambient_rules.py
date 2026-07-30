"""ambient 分类规则表。人工审定的例外写进 AMBIENT_FUNC_EXCEPTIONS（Task 9 检查点）。"""
SYS_FILES = frozenset({
    "config", "snr_lib", "snr_common", "snr_mainmenu", "snr_story_main",
    "snr_fragment_main", "snr_memory", "snr_novel", "snr_music", "snr_graphic",
})
# "file:func" -> 判定理由；narrative 文件中被人工认定为 ambient 的函数写在这里
AMBIENT_FUNC_EXCEPTIONS: dict[str, str] = {}
