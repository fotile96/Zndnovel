#import "../template.typ": *

= 章节 2：咒语

#chapter-open(entry: [章节 1 的 #opt("没有约")], unlock: [持有 #card("章节 1 梗概")])[
  Ayano 没有放学后的约定，于是在图书室听 Sakura 讲了一个「绝对灵验的咒语」。本章是靡费最多的一章：多条 Game Over 支线各自对应一张卡，谜题要故意答错一次再答对一次，三张选择卡层层解锁。
]

== 进入章节 2

#story-box(from: "s1s_35_sel", pick: ("没有约",))[
  #card("选择：放学后的约定") 选 #opt("没有约") #arrow #card("没有约") #arrow 因持有 #card("章节 1 梗概")，跳到章节 2。首次进入时既没有 #card("又是一如往常的生活") 也没有 #card("章节 2 梗概")，直接播 #card("又是一如往常的生活") #arrow #gameover
]
#frag-box[
  #make-cards(("又是一如往常的生活", [递 #card("一如往常的生活")]))
]

#story-box(from: "s1s_35_sel", pick: ("没有约",))[
  再走一次 #opt("没有约")。这次『又是一如往常的生活』已经做成卡，进入 #card("夏天的计划")：这一场耗时 100，讲完沙漏直接满 #timeover
]
#frag-box[
  #make-cards(("夏天的计划", [无需递卡]))
]

#story-box(from: "s2s_60", pick: ("不去",))[
  从 #card("夏天的计划") 接着讲（已持卡，跳过）#arrow #card("选择：周末的计划")：默认只有 #opt("不去") #arrow 又回到 #card("又是一如往常的生活") #arrow #gameover
]
#frag-box[
  #make-cards(("选择：周末的计划", [递 #card("又是一如往常的生活")。做成后出现 #opt("去")]))
]

#story-box(from: "s2s_80_sel", pick: ("去", "没什么特别的"))[
  #card("选择：周末的计划") 选 #opt("去") #arrow #card("课间休息") #arrow #card("选择：对咒语的兴趣")：默认三项 #opt("没什么特别的")、#opt("考试拿满分")、#opt("唱歌变好听") 都通向 #card("Sakura的叹息") #arrow #card("又是一如往常的生活") #arrow #gameover
]
#frag-box[
  #make-cards(
    ("课间休息", [依次递 #card("放学后的钱仙")、#card("她的名字")]),
    ("Sakura的叹息", [递 #card("又是一如往常的生活")]),
    ("选择：对咒语的兴趣", [依次递 #card("Sakura的叹息")、#card("不好的结果")。做成后出现 #opt("想两情相悦")]),
  )
]

== 主线：Ayano 的心意与谜题

#story-box(from: "s2s_120_sel", pick: ("想两情相悦",))[
  #card("选择：对咒语的兴趣") 选 #opt("想两情相悦") #arrow #card("章节 2：Ayano")：耗时 100，#timeover
]
#frag-box[
  #make-cards(("章节 2：Ayano", [递 #card("故事的主人公")]))
]

#story-box(from: "s2s_140", pick: ("明确说喜欢", "谜题答错"))[
  从 #card("章节 2：Ayano") 接着讲 #arrow #card("与Yuichi的关系") #arrow #card("选择：对Yuichi的心意")：默认只有 #opt("明确说喜欢") #arrow #card("喜欢Yuichi") #arrow #card("选择：谜题")：未持选择卡时直接进入 Sakura 出的两道谜题。*第一次请故意答错至少一题*，答错走 #card("谜题答错") #timeover
]

#tip-box(title: "谜题答案")[
  两道谜题各三层，全部答对才算「答对」。
  #set par(first-line-indent: 0em)
  #table(
    columns: (auto, 1fr, 1fr, 1fr),
    stroke: 0.4pt + c-line, inset: (x: 6pt, y: 4pt),
    [*谜题 1*], [#opt("普通的家中")], [#opt("与父母有关")], [#opt("女孩一直被关着")],
    [*谜题 2*], [#opt("完全没有问题")], [#opt("原作")], [#opt("原作本身是假货")],
  )
  答对后入手关键词卡 #card("Sakura同学的谜题")。
]

#frag-box[
  #make-cards(
    ("与Yuichi的关系", [无需递卡]),
    ("喜欢Yuichi", [递 #card("Yuichi救下Ayano")]),
    ("谜题答错", [无需递卡，但本轮路线里必须有答错的场景]),
    ("选择：对Yuichi的心意", [递 #card("喜欢Yuichi")。做成后出现 #opt("含糊其辞")]),
  )
]

#story-box(from: "s2s_209", pick: ("游泳池",))[
  从 #card("谜题答错") 接着讲 #arrow #card("出去玩的地方") #arrow #card("选择：出去玩的地方")：默认只有 #opt("游泳池") #arrow #card("游泳池的约定") #arrow #card("图书室") #timeover
]
#frag-box[
  #make-cards(
    ("出去玩的地方", [递 #card("夏天的计划")]),
    ("游泳池的约定", [无需递卡]),
    ("图书室", [递 #card("早晨的教室")]),
  )
]

#story-box(from: "s2s_160_sel", pick: ("含糊其辞", "谜题答对", "游泳池"))[
  回到 #card("选择：对Yuichi的心意") 选 #opt("含糊其辞") #arrow #card("对Yuichi嘛……") #arrow 谜题这次全部答对（入手 #card("Sakura同学的谜题")）#arrow #card("谜题答对") #arrow #card("出去玩的地方") #arrow #card("选择：出去玩的地方") 选 #opt("游泳池") #arrow #card("游泳池的约定") #arrow #card("图书室") #arrow #card("选择：放学后的咒语")：耗时 100，选项弹出前 #timeover
]
#frag-box[
  #make-cards(
    ("对Yuichi嘛……", [无需递卡]),
    ("谜题答对", [无需递卡]),
    ("选择：谜题", [依次递 #card("谜题答对")、#card("谜题答错")。做成后谜题场景出现 #opt("谜题答对")、#opt("谜题答错")、#opt("挑战谜题") 三项，可以直接指定结果不再答题]),
    ("选择：放学后的咒语", [递 #card("选择：谜题")]),
  )
]

== 咒语的三个版本

#card("选择：放学后的咒语") 的选项集取决于*本轮*谜题结果：路线里有 #card("谜题答错") 时只有 #opt("边看夕阳边听歌") 与 #opt("教科书背面写名字")，答对（或用选择卡指定 #opt("谜题答对")）才出现 #opt("橡皮上写名字")。而只有 #opt("橡皮上写名字") 能把故事讲到夜晚。

#story-box(from: "s2s_260_sel", pick: ("橡皮上写名字", "多半吧……"))[
  从 #card("选择：放学后的咒语") 接着讲，这一轮谜题答对了，选 #opt("橡皮上写名字") #arrow #card("橡皮上写名字") #arrow #card("选择：咒语的效果")：默认只有 #opt("多半吧……") 与 #opt("觉得做了也不亏")，先选 #opt("多半吧……") #arrow #card("觉得多半灵验") #arrow #card("咒语完成") #timeover
]
#frag-box[
  #make-cards(
    ("橡皮上写名字", [递 #card("约好了")]),
    ("觉得多半灵验", [无需递卡]),
    ("咒语完成", [无需递卡]),
  )
]

两个 Game Over 结局互为对方做卡的前置（『Yuichi的背影』要递『中庭的人群』，『回荡在走廊的声音』要递『Yuichi的背影』），而且分别在两条支线上，所以要来回走三趟：

#story-box(from: "s2s_160_sel", pick: ("明确说喜欢", "谜题答对", "游泳池", "橡皮上写名字", "多半吧……"))[
  回到 #card("选择：对Yuichi的心意") 选 #opt("明确说喜欢") #arrow #opt("谜题答对") #arrow #opt("游泳池") #arrow #opt("橡皮上写名字") #arrow #opt("多半吧……") #arrow #card("咒语完成") #arrow 这一轮讲的是「喜欢」那条线，进 #card("回荡在走廊的声音")（入手 #card("中庭的人群")）#arrow #gameover。这一趟只为拿『中庭的人群』，不做卡。
]
#story-box(from: "s2s_160_sel", pick: ("含糊其辞", "谜题答对", "游泳池", "橡皮上写名字", "觉得做了也不亏"))[
  回到 #card("选择：对Yuichi的心意") 选 #opt("含糊其辞") #arrow #opt("谜题答对") #arrow #opt("游泳池") #arrow #opt("橡皮上写名字") #arrow #opt("觉得做了也不亏") #arrow #card("咒语完成") #arrow 没讲过「喜欢」就进 #card("Yuichi的背影") #arrow #gameover
]
#frag-box[
  #make-cards(
    ("觉得做了也不亏", [递 #card("觉得多半灵验")]),
    ("Yuichi的背影", [递 #card("中庭的人群")]),
  )
]
#story-box(from: "s2s_160_sel", pick: ("明确说喜欢", "谜题答对", "游泳池", "橡皮上写名字", "多半吧……"))[
  再走一次 #opt("明确说喜欢") #arrow #opt("谜题答对") #arrow #opt("游泳池") #arrow #opt("橡皮上写名字") #arrow #opt("多半吧……") #arrow #card("回荡在走廊的声音") #arrow #gameover，让它回到时间轴上。
]
#frag-box[
  #make-cards(
    ("回荡在走廊的声音", [递 #card("Yuichi的背影")。做成后额外获得 #card("绝对灵验的咒语")]),
    ("选择：咒语的效果", [递 #card("绝对灵验的咒语")。做成后出现 #opt("绝对灵验")，并获得关键词卡 #card("Ayano")]),
  )
]

#story-box(from: "s2s_340_sel", pick: ("绝对灵验",))[
  回到 #card("选择：咒语的效果") 选 #opt("绝对灵验") #arrow #card("觉得绝对灵验") #arrow #card("咒语完成") #arrow 三个条件（喜欢、橡皮、绝对灵验）齐备，进入 #card("夜晚的走廊")：耗时 100，#timeover
]
#frag-box[
  #make-cards(
    ("觉得绝对灵验", [无需递卡]),
    ("夜晚的走廊", [依次递 #card("Sakura的叹息")、#card("谜题答对")、#card("橡皮上写名字")、#card("觉得绝对灵验")]),
  )
]
#story-box(from: "s2s_500")[
  从 #card("夜晚的走廊") 接着讲 #arrow #card("游泳池") #arrow #card("咒语的效果") #arrow #complete
]
#frag-box[
  #make-cards(
    ("游泳池", [无需递卡]),
    ("选择：出去玩的地方", [依次递 #card("游泳池")、#card("有谁在呼唤")。做成后出现 #opt("天象馆")]),
  )
]

== 收尾：天象馆与另一种咒语

#story-box(from: "s2s_260_sel", pick: ("边看夕阳边听歌", "多半吧……"))[
  先补另一种咒语：回到 #card("选择：放学后的咒语") 选 #opt("边看夕阳边听歌") #arrow #card("咒语，成功了……？") #arrow 效果选 #opt("多半吧……") #arrow #card("咒语完成") #arrow #card("回荡在走廊的声音") #arrow #gameover
]
#frag-box[
  #make-cards(("咒语，成功了……？", [依次递 #card("回荡在走廊的声音")、#card("Yuichi的背影")]))
]
#story-box(from: "s2s_220_sel", pick: ("天象馆", "橡皮上写名字", "绝对灵验"))[
  回到 #card("选择：出去玩的地方") 选 #opt("天象馆") #arrow #card("天象馆的约定") #arrow #card("图书室") #arrow 咒语照旧选 #opt("橡皮上写名字")、#opt("绝对灵验") #arrow #card("夜晚的走廊") #arrow #card("天象馆") #arrow #card("咒语的效果") #arrow #complete
]
#frag-box[
  #make-cards(
    ("天象馆的约定", [无需递卡]),
    ("天象馆", [无需递卡]),
    ("咒语的效果", [章节终卡 #cn(61)。需先持有 #card("咒语，成功了……？")；依次递 #card("夜晚的走廊")、#card("天象馆")]),
  )
]

做成 #card("咒语的效果") 后进入现实层「章节 2 读完」：傍晚的操场、千秋的家庭情况。获得 #card("章节 2 梗概") #cn(134)。
