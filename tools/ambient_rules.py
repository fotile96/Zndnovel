"""ambient 分类规则表。人工审定的例外写进 AMBIENT_FUNC_EXCEPTIONS（Task 9 检查点）。"""
SYS_FILES = frozenset({
    "config", "snr_lib", "snr_common", "snr_mainmenu", "snr_story_main",
    "snr_fragment_main", "snr_memory", "snr_novel", "snr_music", "snr_graphic",
})
# "file:func" -> 判定理由；narrative 文件中被人工认定为 ambient 的函数写在这里
AMBIENT_FUNC_EXCEPTIONS: dict[str, str] = {}

# "file:func" -> 判定理由；sys 文件中被人工认定为 narrative（上时间轴）的函数
# 2026-07-30 用户审定：探索到场语音与 Time over 演出是玩家在时间轴上实际经历的剧情文本
NARRATIVE_FUNC_EXCEPTIONS: dict[str, str] = {
    "snr_common:comSectionMapmoveAyanoIn": "故事层アヤノ探索场景到场语音，随 Story 模式播出",
    "snr_common:comSectionStoryEndAyanoTime": "Time over 演出旁白（彩野记忆中断），沙漏满时在时间轴上播出",
}
