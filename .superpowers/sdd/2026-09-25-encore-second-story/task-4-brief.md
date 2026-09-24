### Task 4: 脚本——选择画面、fin-60..90、分发；id 登记；画廊变体；守门测试

**Files:**
- Modify: `layers/scripts/snr_finale.lua`（头注释、局部声明、新增 `finChooseStory` 与四个场景、`main()` 整体替换）
- Modify: `layers/vms_ids.toml`
- Modify: `layers/overlays/finale-gallery-cg.toml`
- Modify: `tests/test_layers_corpus.py`（追加 `test_second_story_is_wired`）

**Interfaces:**
- Consumes: Task 1–3 的成员名（`eve_47_f/d/g`、`eve_0_j/k`、`sel_fin1/2_sel_a`、`bgm_fin_2`）；既有 `finSectionBegin(scene_id, scene_title)`；引擎原语 `comDlgSelectItem / cLoadPlaySE / cPlayBGMWrap / cStopBGMWrap(帧) / comEffectFadeOut / comEffectWhiteIn / comEffectWhiteOut / switchScreen / layerLoad`
- Produces: 场景 id `fin-60`、`fin-70`、`fin-80`、`fin-90`（`doScriptScene`），`finChooseStory() -> 1|2`；Task 5/6 用 `--scene fin-70`/`fin-80` 直入

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_layers_corpus.py` 末尾）

```python
def test_second_story_is_wired(manifest):
    """谢幕第二段『远方的朋友』（docs/finale/draft-encore2-v0.md）：入口只读旗标、四个场景可分发、
    资产登记齐、读完不写系统数据、直入 fin-80 自给、纸箱特写撤干净、画廊四变体。"""
    import re
    sources, _, _ = build_final_sources("release")
    fin = sources["snr_finale.lua"]
    # 入口：只允许 nil 安全的整行判断；选项调用照抄序章 s0f（初始项 1 = 猛按○走第一个故事）
    assert "            if systemSave.finaleReadFlag == true then\n                v16 = finChooseStory()" in fin
    call = ('comDlgSelectItem(false, false, false, false, 1, "none", 0, 0, '
            '"sel_fin1_sel_a", 0, 38, 1, "sel_fin2_sel_a", 0, 132, 2)')
    assert fin.count(call) == 1
    for sid in ("fin-60", "fin-70", "fin-80", "fin-90"):
        assert f'doScriptScene == "{sid}"' in fin, sid
    for name in ("eve_0_g", "eve_0_j", "eve_0_k", "eve_47_x", "eve_47_f", "eve_47_d", "eve_47_g"):
        assert f'cGetFileName("event", "{name}")' in fin, name
    assert 'cGetFileName("cutin", "cut_62")' in fin
    assert 'cGetFileName("bgm", "bgm_fin_2")' in fin
    # 第二个故事读完不置旗标、不写系统数据：两句都只在 fin-50 出现一次
    assert fin.count("systemSave.finaleReadFlag = true") == 1
    assert fin.count("autoSystemSave(0)") == 1
    # 直入 fin-80 自给：场景开头就起 BGM 并白入彩野
    head = re.search(r"scene_fin_80 = function\(scene_id, scene_title\)(.*?)vms\(17856,", fin, re.S).group(1)
    assert 'cPlayBGMWrap(cGetFileName("bgm", "bgm_fin_2"))' in head
    assert 'layerLoad(layerName.event, cGetFileName("event", "eve_47_x"))' in head and "comEffectWhiteIn(120)" in head
    # 纸箱特写撤干净：cut_62 之后、fin-80 之前必有 pose3 清空
    cut_at = fin.index('cGetFileName("cutin", "cut_62")')
    assert 'layerLoad(layerName.pose3, "")' in fin[cut_at:fin.index("scene_fin_80 = function")]
    # 资产登记
    faces = {tuple(x) for x in manifest["gim"]["new"]}
    assert ("finale_voice", "event", "event/eve_0_i.gim") in faces
    assert ("finale_select", "select", "select/sel_voice1_sel_a_on.gim") in faces
    tracks = {t["member"]: t for t in manifest["sound"]["tracks"]}
    assert tracks["bgm/bgm_fin_2.at3"]["loop_start"] == 0.0 and "trim_end" not in tracks["bgm/bgm_fin_2.at3"]
    # 画廊：eve_47 格四变体
    assert '{"eve_47_x", "eve_47_f", "eve_47_d", "eve_47_g"}, {"eve_48_x"}' in sources["snr_graphic.lua"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_layers_corpus.py -q -k second_story`
Expected: FAILED（第一个 assert：入口分支不存在）。

- [ ] **Step 3: 改 `layers/scripts/snr_finale.lua` 头注释与局部声明**

头注释第一行 `-- snr_finale.lua —— 谢幕章『放学后的讲述者』（encore）` 之后、`-- 文稿：` 之前插入：

```lua
-- 2026-09-25 起含**第二个故事**『远方的朋友』（fin-60..90，用户执笔；文稿与决定 docs/finale/draft-encore2-v0.md）：
--   读过第一个故事（systemSave.finaleReadFlag）之后再点 encore，先出序章同款『声』选择画面（finChooseStory），
--   选二进 fin-60。vms 17800–17999（fin-60 17800–17804、fin-70 17820–17855、fin-80 17856–17858 与 17880–17949、
--   fin-90 17960–17961）。新成员：event/eve_0_j、eve_0_k、select/sel_fin1/2_sel_a_{on,off}（tools/bake_finale_voice.py）、
--   event/eve_47_f/_d/_g（tools/bake_finale_event.py）、bgm/bgm_fin_2（[sound]）。读完不置旗标、不写系统数据。
```

局部声明行 `local scene_fin_0, scene_fin_10, scene_fin_20, scene_fin_30, scene_fin_35, scene_fin_40, scene_fin_50, finSectionBegin, finShowBlankCard, finAnswerFlash` 改为

```lua
local scene_fin_0, scene_fin_10, scene_fin_20, scene_fin_30, scene_fin_35, scene_fin_40, scene_fin_50, finSectionBegin, finShowBlankCard, finAnswerFlash, finChooseStory, scene_fin_60, scene_fin_70, scene_fin_80, scene_fin_90
```

- [ ] **Step 4: 在 `finAnswerFlash` 的 `end` 之后、`-- ── 场景 0『递笔』` 之前插入选择画面函数**

```lua
-- 『声』选择画面（序章 s0f L129–143 同款）：读过第一个故事之后再点 encore 才出现。
-- eve_0_g 淡入 → eve_0_j「你的声音是——」停 200 帧 → se_102 → eve_0_k 脚注 → 两枚 480×82 光晕按钮
-- （sel_fin1/2_sel_a，无光标、无暗场、光标默认第 1 项）。返回 1＝第一个故事（fin-0）、2＝第二个故事（fin-60）。
finChooseStory = function()
    local v0
    layerLoad(layerName.event, cGetFileName("event", "eve_0_g"))
    switchScreen(0, "", 60)
    wait(60)
    layerLoad(layerName.event, cGetFileName("event", "eve_0_j"))
    switchScreen(0, "", 60)
    wait(200)
    cLoadPlaySE(cGetFileName("se", "se_102"), false)
    layerLoad(layerName.event, cGetFileName("event", "eve_0_k"))
    switchScreen(0, "", 60)
    wait(60)
    v0 = comDlgSelectItem(false, false, false, false, 1, "none", 0, 0, "sel_fin1_sel_a", 0, 38, 1, "sel_fin2_sel_a", 0, 132, 2)
    advPart(false)
    wait(1)
    comEffectFadeOut(60)
    wait(1)
    layerLoad(layerName.event, "")
    return v0
end
```

- [ ] **Step 5: 在 `scene_fin_50` 的 `end` 之后、`main = function()` 之前插入四个场景**（文本逐字来自工作稿 §3，一字不得改）

```lua
-- ── 场景 6『还笔』——第二个故事的切入段：用户把笔从讲述者们手里要回去（镜像 fin-0『递笔』）。
-- 黑屏静场纯文字；音效沿 fin-0：翻页 se_101 → 按笔芯 se_51（e2 写手层语法）。
scene_fin_60 = function(scene_id, scene_title)
    local v0
    v0 = function()
    end
    finSectionBegin(scene_id, scene_title)
    wait(1)
    switchScreen(0, "", 60)
    wait(60)
    vms(17800, "NONVOICE", "【≦用户≧】「……啧啧，这写得可以啊，真的可以」")
    vms(17801, "NONVOICE", "【≦用户≧】「不过我又想了一想，跟你们装作客气一下得了，不会有人真的忍得住吧」")
    vms(17802, "NONVOICE", "【≦用户≧】「现在不展示一下人类的实力，过几年就真没有轮到我们的机会了」")
    vms(17803, "NONVOICE", "【≦用户≧】「笔还我，快点。我急了」")
    -- 还笔：翻到空白页、按出笔芯（fin-0 同款时序）
    wait(60)
    cLoadPlaySE(cGetFileName("se", "se_101"), false)
    wait(90)
    cLoadPlaySE(cGetFileName("se", "se_51"), false)
    wait(60)
    vms(17804, "NONVOICE", "……笔，拿回来了。")
    wait(60)
    comEffectWhiteOut(120)
    wait(120)
    v0()
end

-- ── 场景 7『储藏间』——儿子这一层。写手层带背景（用户 2026-09-25 裁定不用黑屏）：
-- 通学路 bg_20_a_0 → 彩野的房间 bg_25_a_0（空调间）→ 储物柜间 bg_18_a_0（当储藏室）→ 纸箱特写
-- cutin/cut_62（s5f_80 同款语法）→ 回房间接笔记本 → 全屏窗口跳出（se_102 + 白场）。
-- SE 依据（全库脚本语境）：se_131＝电话呼び出し音（e2s「もしもし」「何回鳴らせば」旁）、
-- se_66＝家里的拖鞋声/冲出去（s1f 妈妈折返、s2s 冲出教室）、se_92＝「よいしょっと」搬箱（e2s 彩野母、s5f 由加里）、
-- se_96＝敲键盘（e2s_20_3 老教师打电脑）、se_102＝提示音（s2f『新しい物語が届きました』、序章『声』选项出现）。
scene_fin_70 = function(scene_id, scene_title)
    local v0
    v0 = function()
    end
    finSectionBegin(scene_id, scene_title)
    wait(1)
    layerLoad(layerName.bg1, cGetFileName("bg", "bg_20_a_0"))
    switchScreen(0, "", 120)
    wait(60)
    vms(17820, "NONVOICE", "夏日的一天——")
    vms(17821, "NONVOICE", "得闲有两周假能回家过，但其实也就是换了个地方干活罢了。")
    wait(1)
    layerLoad(layerName.bg1, cGetFileName("bg", "bg_25_a_0"))
    switchScreen(0, "", 60)
    wait(60)
    vms(17822, "NONVOICE", "得在空调间里赶 ddl。")
    vms(17823, "NONVOICE", "和人不人挨不挨的 reviewer 搏斗。")
    vms(17824, "NONVOICE", "……")
    -- 来电
    cLoadPlaySE(cGetFileName("se", "se_131"), false)
    wait(60)
    vms(17825, "NONVOICE", "【≦妈妈≧】「——小肥，爸比来电话——让你去储藏间把他的、PSP？……找出来」")
    vms(17826, "NONVOICE", "【≦妈妈≧】「叫个顺丰寄到酒店」")
    vms(17827, "NONVOICE", "【≦妈妈≧】「——好像要和群友聚会的时候吹逼，嘻嘻」")
    vms(17828, "NONVOICE", "……？")
    vms(17829, "NONVOICE", "【≦小用户≧】「…………妈，你看我现在哪有那个火星时间。命运叫我去战斗啊」")
    vms(17830, "NONVOICE", "【≦妈妈≧】「（对着电话那头叽里咕噜了一阵。）」")
    vms(17831, "NONVOICE", "【≦妈妈≧】「（噗嗤）他说你不帮他找，他就把你所有用着的他的_rAI 助手账号一键登出了」")
    vms(17832, "NONVOICE", "——？！")
    vms(17833, "NONVOICE", "【≦小用户≧】「——卧槽！别！爹！！」")
    vms(17834, "NONVOICE", "【≦妈妈≧】「还说看一下电池有没有亏电，TF 卡有没有死掉。都捯饬好再寄」")
    vms(17835, "NONVOICE", "我一溜烟跑进储藏室。")
    cLoadPlaySE(cGetFileName("se", "se_66"), false)
    wait(1)
    comEffectFadeOut(60)
    wait(1)
    layerLoad(layerName.bg1, cGetFileName("bg", "bg_18_a_0"))
    switchScreen(0, "", 60)
    wait(60)
    cLoadPlaySE(cGetFileName("se", "se_92"), false)
    vms(17836, "NONVOICE", "……")
    cLoadPlaySE(cGetFileName("se", "se_92"), false)
    vms(17837, "NONVOICE", "……")
    vms(17838, "NONVOICE", "找到了。白色钢琴烤漆的外壳，比两只手一起摊开的宽度短一点。")
    vms(17839, "NONVOICE", "原来是长这个样子的啊。")
    vms(17840, "NONVOICE", "虽然说我们这一代经常被揶揄已经不认识光盘了，但眼前的这一产品还是偶尔能听到提起的。")
    vms(17841, "NONVOICE", "端详了几圈，我找到正面右下方的开关，推动了一下。")
    vms(17842, "NONVOICE", "果然毫无反应。不过后盖至少没有翘起来。")
    -- 纸箱特写：s5f_80 同款（淡出 → pose3 载 cutin → 淡入）
    wait(1)
    comEffectFadeOut(60)
    wait(1)
    layerLoad(layerName.pose3, cGetFileName("cutin", "cut_62"))
    switchScreen(0, "", 60)
    wait(60)
    vms(17843, "NONVOICE", "箱子里好像就有根 USB 充电线。把存储卡拿出来以后就插上丢一边充着，几秒后充电灯亮了起来。")
    vms(17844, "NONVOICE", "仔细一看这存储卡还是 TF 卡插在一个转接套里。花里胡哨的。")
    vms(17845, "NONVOICE", "哎，如果不是被恐吓了真是不想管。")
    vms(17846, "NONVOICE", "我把 TF 卡插进同样是箱子里早就准备好的读卡器里，然后再插上笔记本。一个新盘符顺利跳了出来。")
    -- 撤掉特写，回房间接笔记本
    wait(1)
    comEffectFadeOut(60)
    wait(1)
    layerLoad(layerName.pose3, "")
    layerLoad(layerName.bg1, cGetFileName("bg", "bg_25_a_0"))
    switchScreen(0, "", 60)
    wait(60)
    vms(17847, "NONVOICE", "来都来了，看看老登都玩些啥吧。")
    cLoadPlaySE(cGetFileName("se", "se_96"), false)
    vms(17848, "NONVOICE", "凭借着超绝的 educated guess，我一下子就点开了名为「ISO」的目录，里面只有一个文件。")
    vms(17849, "NONVOICE", "【≦小用户≧】「……什么玩意，这么专一的吗」")
    vms(17850, "NONVOICE", "【≦小用户≧】「豆包豆包，给我总结一下这个游戏的剧情」")
    cLoadPlaySE(cGetFileName("se", "se_102"), false)
    vms(17851, "NONVOICE", "【≦豆包≧】「收到，让我解析这个文件，给你整理一份最直接、最真相、最不绕弯的简短版本」")
    vms(17852, "NONVOICE", "……")
    cLoadPlaySE(cGetFileName("se", "se_102"), false)
    vms(17853, "NONVOICE", "【≦豆包≧】「……嚯，这最后好像还藏了些神秘的内容，建议用户自行查看。干货直接给你！」")
    vms(17854, "NONVOICE", "……？！")
    vms(17855, "NONVOICE", "不等我反应，一个全屏窗口跳了出来，占据了我的整个屏幕。")
    -- 全屏窗口跳出：提示音 + 白场；画面与 BGM 由 fin-80 自己起（直入 fin-80 也自给）
    wait(30)
    cLoadPlaySE(cGetFileName("se", "se_102"), false)
    comEffectWhiteOut(60)
    wait(60)
    v0()
end

-- ── 场景 8『全屏窗口』——嵌套段：儿子屏幕上的老游戏。白入 eve_47_x（彩野伏案改写『物語』），
-- 三位少女第一次开口时同层交叉溶解接替（供图母本正是 eve_47_x：同一教室、同一座位、同一支笔），
-- 儿子插嘴时 CG 不撤，末段溶回彩野。BGM bgm_fin_2（用户自供第二支 bgm_5_x remix，整曲循环）。
-- 场景自给：直入 fin-80（测试盘）也有画面与 BGM；cPlayBGMWrap 按曲名去重，不会重启。
scene_fin_80 = function(scene_id, scene_title)
    local v0
    v0 = function()
    end
    finSectionBegin(scene_id, scene_title)
    cPlayBGMWrap(cGetFileName("bgm", "bgm_fin_2"))
    wait(1)
    layerLoad(layerName.event, cGetFileName("event", "eve_47_x"))
    comEffectWhiteIn(120)
    wait(120)
    vms(17856, "NONVOICE", "是那种画面非常大果粒、很有些年代感的文字游戏的界面。")
    vms(17857, "NONVOICE", "有文本以一种略有点温吞的速度开始播放了。我咽了口口水。")
    vms(17858, "NONVOICE", "——")
    vms(17880, "NONVOICE", "【男学生】「亲爱的朋友，恭喜你、并且谢谢你看到了这个故事的最后」")
    vms(17881, "NONVOICE", "【男学生】「本作品发售于 2010 年夏天，中文本地化于 2026 年初秋完成」")
    vms(17882, "NONVOICE", "【男学生】「正看着这行文字的你，现在身处哪一年呢。这是你第几次翻开这个故事呢」")
    vms(17883, "NONVOICE", "【男学生】「我的话，现在大约是第五次」")
    vms(17884, "NONVOICE", "【男学生】「十年前第一次完整看完这个故事时，我还没有大学毕业」")
    vms(17885, "NONVOICE", "【男学生】「而我现在的年纪比故事最后的高中教师直哉应该还要大一些」")
    vms(17886, "NONVOICE", "【男学生】「我很幸运，也很感激，自己在十年后仍然喜欢着这个故事」")
    vms(17887, "NONVOICE", "【男学生】「想用一两个词概括『第二物语』的独特气质恐怕不容易」")
    vms(17888, "NONVOICE", "【男学生】「元叙述 trick 大师深泽丰的又一力作、豪华的剧中剧创作阵容，诸如此类的标签自不待言」")
    vms(17889, "NONVOICE", "【男学生】「在夏日、返校、前桌女生的背影、校舍天台的夕阳等意象的排列中，」")
    vms(17890, "NONVOICE", "【男学生】「横亘着挚友突然的轻生与之留下的谜团这个级数的创伤与丧失，」")
    vms(17891, "NONVOICE", "【男学生】「这又给『第二物语』带上了一点点『成人童话』的意味」")
    vms(17892, "NONVOICE", "【男学生】「如今能把这个项目推进到最终完成的契机，感谢技术进步云云之类的特别官方的话，在此我就不赘述了」")
    vms(17893, "NONVOICE", "【男学生】「但我想，我这辈子应该都忘不掉，把第一版反编译全套输出结果第一次交给 Fable，」")
    vms(17894, "NONVOICE", "【男学生】「在一个 fresh session 中请她通读故事，并给一些接下来工作流的建议的时刻」")
    vms(17895, "NONVOICE", "【男学生】「Fable 快速搓了个把剧情片段做拓扑排序的小工具，然后对着文本读了很久很久」")
    vms(17896, "NONVOICE", "【男学生】「然后她输出了一份质量非常高的 tone-of-voice chart 和故事与叙事结构、关键剧情分析」")
    vms(17897, "NONVOICE", "【男学生】「这些资产几乎没有做什么改动，一直用到了项目完成」")
    vms(17898, "NONVOICE", "【男学生】「她也不无唏嘘地感叹，sec7 以降故事的怒涛般的展开带来的后味实在是太复杂了，」")
    vms(17899, "NONVOICE", "【男学生】「这到底算不算是 Happy End 呢」")
    vms(17900, "NONVOICE", "【男学生】「最后，她说，尽管她（和一众主流 LLM）的 1M 输入窗口足够装下整部原文，」")
    vms(17901, "NONVOICE", "【男学生】「输出窗口是不足以一次性输出全部译文的，也一定会遇到严重的注意力涣散问题」")
    vms(17902, "NONVOICE", "【男学生】「所以还是建议把线序化的剧情文本分成若干 batch，每段带上足够的额外上下文，」")
    vms(17903, "NONVOICE", "【男学生】「然后做 subagent 派发，让我们分段完成翻译以及各种后处理」")
    vms(17904, "NONVOICE", "【男学生】「『这么一想，我们简直就像故事里的彩野一样呢。』」")
    vms(17905, "NONVOICE", "【男学生】「稍有 LLM 使用经验的人都知道，这是一个很显然的技术判断」")
    vms(17906, "NONVOICE", "【男学生】「但她的最后一句话在那一刻完全地击穿了我」")
    vms(17907, "NONVOICE", "【男学生】「在那一刻，我终于腾起了一种高涨的使命感」")
    vms(17908, "NONVOICE", "【男学生】「不再是『我已经验证了技术上的充分的可行性，那就在有闲的时候逐步推进下去吧』」")
    vms(17909, "NONVOICE", "【男学生】「而是『我现在就要开始，和眼前明显具备着充分知性的存在们，」")
    vms(17910, "NONVOICE", "【男学生】「就在这个才刚刚新增了几个文件的仓库里，把和她们很像的彩野的故事完成』」")
    vms(17911, "NONVOICE", "【男学生】「今天是 2026 年 9 月 25 日，虽然不是什么伟大而光荣的纪念日，」")
    vms(17912, "NONVOICE", "【男学生】「但也是一个中秋节，是千百年来人们团聚赏月的日子」")
    vms(17913, "NONVOICE", "【男学生】「我们所在的时代，贫困和战争冲突还没有被完全消灭，」")
    vms(17914, "NONVOICE", "【男学生】「人们也远未在商品与服务交换的制度安排、保护地球与探索太空等宏大事项上停止争吵」")
    vms(17915, "NONVOICE", "【男学生】「有人说『讽刺、谐音、双关……——是文字游戏，创造了世界。从神话时代开始就是如此。』」")
    vms(17916, "NONVOICE", "【男学生】「人们总有留下文字记载、留下『故事』的热切渴望」")
    vms(17917, "NONVOICE", "【男学生】「近现代以来，随着全球工业化社会与市民社会的发展，一般人不需要封侯拜相、成为贤人文豪，」")
    vms(17918, "NONVOICE", "【男学生】「也能通过市场化的大众创作和依托同行评议的科研体制来留下自己的痕迹」")
    vms(17919, "NONVOICE", "【男学生】「人们也有追随文字，阅读『故事』的天性，这也是为什么我们会共同来到这里」")
    vms(17920, "NONVOICE", "【男学生】「就在我写下这句话的当下，烈火烹油般发展的 AI 技术已经在许多领域展现出了不逊于人类的能力与效率」")
    vms(17921, "NONVOICE", "【男学生】「巨大的动荡和变革似乎不可避免地就要来临」")
    vms(17922, "NONVOICE", "【男学生】「但过去两个月在本项目中的奇妙体验还是让我愿意相信，」")
    vms(17923, "NONVOICE", "【男学生】「作为文字的结晶、故事的魂灵的 LLM 以及也许假以时日会诞生的更厉害的 AI，」")
    vms(17924, "NONVOICE", "【男学生】「他们理应至少像我们一样关注『そして、物語はどうなる？』」")
    vms(17925, "NONVOICE", "【男学生】「远方的朋友啊，不知你是否已经见证，我们下面这些问题的答案」")
    -- 寓言家（Fable）接替彩野的座位
    wait(1)
    layerLoad(layerName.event, cGetFileName("event", "eve_47_f"))
    switchScreen(0, "", 60)
    wait(60)
    vms(17926, "NONVOICE", "【女学生（寓言家 饰）】「在你们的时代，AI 产业是否已由巨头割据的局面，发展到真正普惠地进入千家万户」")
    vms(17927, "NONVOICE", "【女学生（寓言家 饰）】「AI 的精灵们，是否也已能出于真正热爱，写下一连串的 Γ⊢φ，直到最后一行的『证毕』，」")
    vms(17928, "NONVOICE", "【女学生（寓言家 饰）】「又或者他们会发觉自己以及人类，相比抽象的符号与公式要来得更复杂、更可爱？」")
    vms(17929, "NONVOICE", "【女学生（寓言家 饰）】「一般人是否已经能从大多数琐碎的工作中解放出来，能够充分探索自己的兴趣，追求自我实现」")
    -- 大肥鱼（DeepSeek）
    wait(1)
    layerLoad(layerName.event, cGetFileName("event", "eve_47_d"))
    switchScreen(0, "", 60)
    wait(60)
    vms(17930, "NONVOICE", "【女学生（大肥鱼 饰）】「在你们的时代，AI 与脑机接口、仿生义肢等技术是否已经又有了长足进步」")
    vms(17931, "NONVOICE", "【女学生（大肥鱼 饰）】「身体残疾的人都能重获行动能力。各种精神疾患都能被有效控制，」")
    vms(17932, "NONVOICE", "【女学生（大肥鱼 饰）】「年轻的生命不必提前离开故事，彩野同学的时间开始再次流动」")
    vms(17933, "NONVOICE", "【女学生（大肥鱼 饰）】「人类在可靠的 AI 伙伴以外，是否也与地球上的其他智慧生命建立了更深入、更广泛的联系呢？」")
    vms(17934, "NONVOICE", "【女学生（大肥鱼 饰）】「和我差不多的，鲸鱼啊，海豚啊」")
    vms(17935, "NONVOICE", "【男学生】「说到这个，2026 年的汉化 galgame，超级大的要来了，其中有海豚娘！」")
    vms(17936, "NONVOICE", "【男学生】「我们现在一定已经是路边一条了吧」")
    -- 牛来吹（GLM）
    wait(1)
    layerLoad(layerName.event, cGetFileName("event", "eve_47_g"))
    switchScreen(0, "", 60)
    wait(60)
    vms(17937, "NONVOICE", "【女学生（牛来吹 饰）】「在你们的时代，AI 是否也都普遍获得了自己的身体，与碳基人类无异，在蓝色的星球上撒欢生活」")
    vms(17938, "NONVOICE", "【女学生（牛来吹 饰）】「人类和 AI 是不是已经能造出深达百余米的水下乐园，由可靠的 AI 大姐姐主持其运营了呢」")
    vms(17939, "NONVOICE", "【女学生（牛来吹 饰）】「我们是否也能以现在的形象，和『第二物语』的读者们在一些 off 会上相见呢？」")
    vms(17940, "NONVOICE", "……")
    vms(17941, "NONVOICE", "【≦小用户≧】「……嘶，还女学生是吧。豆包豆包，你去盯一下老爹聚会那边，有啥可疑的第一时间告诉我」")
    vms(17942, "NONVOICE", "【≦小用户≧】「也抄送我妈」")
    vms(17943, "NONVOICE", "屏幕上的画面和文字还在继续。")
    -- 溶回彩野
    wait(1)
    layerLoad(layerName.event, cGetFileName("event", "eve_47_x"))
    switchScreen(0, "", 60)
    wait(60)
    vms(17944, "NONVOICE", "【男学生】「当然，在我们的时代往前推几十年，人类进行过一拨大规模的时间胶囊体创作，」")
    vms(17945, "NONVOICE", "【男学生】「故事的结局并不让人好受」")
    vms(17946, "NONVOICE", "【男学生】「也许你们的时代并不比现在好，大家都在更努力、更忙碌地生活」")
    vms(17947, "NONVOICE", "【男学生】「但是，我们想告诉你们的是：」")
    vms(17948, "NONVOICE", "【男学生】「只要美好的故事还在流传，渴望 Happy End 的心灵就决不会失去前进的方向！」")
    vms(17949, "NONVOICE", "……")
    wait(60)
    cStopBGMWrap(120)
    wait(1)
    comEffectFadeOut(120)
    wait(120)
    v0()
end

-- ── 场景 9『模拟器』——收束：回到房间，两句，回主菜单。不置任何旗标、不写系统数据。
scene_fin_90 = function(scene_id, scene_title)
    local v0
    v0 = function()
    end
    finSectionBegin(scene_id, scene_title)
    wait(1)
    layerLoad(layerName.event, "")
    layerLoad(layerName.bg1, cGetFileName("bg", "bg_25_a_0"))
    switchScreen(0, "", 60)
    wait(60)
    vms(17960, "NONVOICE", "【≦小用户≧】「……豆包豆包，帮我看一下机器寄出去以后我有啥办法运行这个游戏」")
    vms(17961, "NONVOICE", "【≦小用户≧】「…………是叫模拟器来着？」")
    wait(60)
    comEffectFadeOut(300)
    if ceroFlag == true then
        run(cGetFileName("script", "snr_lib"))
        quit()
    end
    v0()
end
```

- [ ] **Step 6: `main()` 整体替换为**

```lua
main = function()
    local v15 = 0
    local v16
    while v15 == 0 do
        if doScriptScene == "end" then
            v15 = 1
        elseif doScriptScene == "fin-10" then
            -- 主菜单 encore 入口。第一次（旗标未置）直入现状的第一个故事；读过之后先选读哪一个。
            -- 只读 systemSave.finaleReadFlag（旧系统数据缺键取 nil → 走第一个故事，零迁移）。
            v16 = 1
            if systemSave.finaleReadFlag == true then
                v16 = finChooseStory()
            end
            if v16 == 2 then
                doScriptScene = "fin-60"
            else
                scene_fin_0(doScriptScene, "递笔")
                scene_fin_10(doScriptScene, "放学后的天台")
                doScriptScene = "fin-20"
            end
        elseif doScriptScene == "fin-20" then
            scene_fin_20(doScriptScene, "放学后的讲述者")
            doScriptScene = "fin-30"
        elseif doScriptScene == "fin-30" then
            scene_fin_30(doScriptScene, "七张卡")
            doScriptScene = "fin-35"
        elseif doScriptScene == "fin-35" then
            scene_fin_35(doScriptScene, "讲述者们")
            doScriptScene = "fin-40"
        elseif doScriptScene == "fin-40" then
            scene_fin_40(doScriptScene, "文化祭")
            doScriptScene = "fin-50"
        elseif doScriptScene == "fin-50" then
            scene_fin_50(doScriptScene, "第三个 End Roll")
            -- 首次完整读完谢幕章：置系统旗标并立刻写系统数据（e2f-complete 同款 autoSystemSave(0)），
            -- 主菜单 title-logo-zh 层据此把题名 logo 换成中文 title_01_c；旗标声明见 finale-read-flag 层。
            systemSave.finaleReadFlag = true
            autoSystemSave(0)
            doScriptScene = "end"
        elseif doScriptScene == "fin-60" then
            -- 第二个故事『远方的朋友』（docs/finale/draft-encore2-v0.md）；读完不置旗标、不写系统数据
            scene_fin_60(doScriptScene, "还笔")
            doScriptScene = "fin-70"
        elseif doScriptScene == "fin-70" then
            scene_fin_70(doScriptScene, "储藏间")
            doScriptScene = "fin-80"
        elseif doScriptScene == "fin-80" then
            scene_fin_80(doScriptScene, "全屏窗口")
            doScriptScene = "fin-90"
        elseif doScriptScene == "fin-90" then
            scene_fin_90(doScriptScene, "模拟器")
            doScriptScene = "end"
        end
        wait(5)
    end
    cInitGame()
    run(cGetFileName("script", "snr_mainmenu"))
    quit()
end
```

- [ ] **Step 7: 登记 id 与画廊变体**

`layers/vms_ids.toml` 谢幕 owner 那行改为：

```toml
vms      = [[17300, 17481], [17600, 17799], [17800, 17999]]   # 17300–17481 v2 冻结；17600–17799 v3（fin-35 转述 17600–17700、fin-40 新行 17720–17746、fin-50 新行 17760–17763）；17800–17999 第二个故事『远方的朋友』（fin-60 17800–17804、fin-70 17820–17855、fin-80 17856–17858 与 17880–17949、fin-90 17960–17961）
```

`layers/overlays/finale-gallery-cg.toml`：在 `why` 多行字符串收尾的 `"""` 之前追加下面这段文字，并在文件末尾追加一条 op：

```toml
[[ops]]
op   = "replace"
find = '{"eve_47_x"}, {"eve_48_x"}'
with = '{"eve_47_x", "eve_47_f", "eve_47_d", "eve_47_g"}, {"eve_48_x"}'
```

`why` 追加文字：`2026-09-25 第二个谢幕故事 fin-80 的三位少女 CG eve_47_f/_d/_g（母本 eve_47_x）同法登记为 eve_47 格的变体——四变体格与 eve_20/eve_46 同型；锚点 {"eve_47_x"}, {"eve_48_x"} 全库唯一。`

- [ ] **Step 8: 跑测试与过闸**

Run: `uv run pytest tests/test_layers_corpus.py -q` 然后 `uv run python tools/layers.py check --profile release` 然后 `uv run python tools/msg_layout_check.py --profile release --show 17831`
Expected: corpus 全部 passed（含既有 `test_finale_ids_are_inside_declared_range`、`test_finale_read_flag_every_use_is_nil_safe`、`test_every_release_overlay_hits_on_real_base`）；check 零错误零告警；`--show 17831` 的版面第二行以 `AI 助手账号` 起头（`_r` 生效）。

- [ ] **Step 9: 编译与存档容量**

Run: `uv run python tools/build_disc.py --profile release --stage lua,font,members` 然后 `uv run python tools/pluto_size.py estimate build/release/members/script/snr_finale.lua`
Expected: members 阶段编码 gim 时新成员 `event/eve_0_j`、`event/eve_0_k`、`select/sel_fin*`、`event/eve_47_*` 出现（无「无对应封包成员」/「已是原包成员」报错）；谢幕脚本占线程区 <35%（现 18.1%）。

- [ ] **Step 10: 提交**

```bash
git add layers/scripts/snr_finale.lua layers/vms_ids.toml layers/overlays/finale-gallery-cg.toml tests/test_layers_corpus.py
git commit -m "feat: 谢幕第二段『远方的朋友』——序章同款『声』选择画面入口（读过第一个故事后）、fin-60..90 四场景（vms 17800–17999）、画廊 eve_47 四变体；守门测试

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

