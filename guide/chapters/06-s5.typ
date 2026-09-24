#import "../template.typ": *

= 章节 5：Sakura 的日记

#chapter-open(entry: [章节 1 的 #card("选择：声音的主人") 选 #opt("Sakura同学")], unlock: [持有 #card("总有一天你会看到的故事。")])[
  本章的讲述方式与前四章不同：日记卡在开头一次性全部到手，之后在*故事模式里*彩野每读完一篇日记，就要你递出下一篇日记的卡。递错有代价，两处连递多张的一错即 Game Over。
]

== 进入章节 5，交出全部梗概

#story-box(from: "s1s_35_sel", pick: ("约好了", "对答卷表示羡慕", "回学校"), quit: "s1s_260_sel")[
  时间轴此时停在章节 3，先把章节 1 重新讲回来，好让『选择：声音的主人』回到时间轴上：#card("选择：放学后的约定") 选 #opt("约好了") #arrow … #arrow #card("选择：Yuichi的答卷") 选 #opt("对答卷表示羡慕") #arrow #card("选择：回学校") 选 #opt("回学校") #arrow … #arrow #card("选择：声音的主人") #tofrag。全部持卡，一路跳过，零耗时。
]
#frag-box[
  #make-cards(("选择：声音的主人", [递 #card("总有一天你会看到的故事。")。做成后出现 #opt("Sakura同学")]))
]
#story-box(from: "s1s_260_sel", pick: ("Sakura同学",))[
  回到 #card("选择：声音的主人") 选 #opt("Sakura同学") #arrow #card("Sakura同学")：耗时 100，#timeover
]
#frag-box[
  #make-cards(("Sakura同学", [卡 177。需先持有 #card("选择：声音的主人")；依次递 #card("章节 1 梗概")、#card("章节 2 梗概")、#card("章节 3A 梗概")、#card("章节 3B 梗概")、#card("章节 4A 梗概")、#card("章节 4B 梗概")、#card("总有一天你会看到的故事。")]))
]

做成后彩野辨认出这是她与 Sakura 的交换日记，一次性获得 #card("章节 5：Sakura")、全部 12 篇 Sakura 日记卡、两篇 Ayano 回信卡与 #card("章节 5：Ayano")。

== 读日记

#warn-box(title: "本章一律不要跳过")[
  日记卡一开始就全部在手，所以本章每个场景开头都会问「是否跳过」，一律选不跳过：跳过 #card("Sakura的日记：7月（未写完）") 就没有去中庭的选择；跳过 #card("Sakura的日记：9月16日（夜）") 直接 #gameover；跳过 #card("Sakura的日记：断片") 拿不到三张关键词卡。持卡场景本来就不耗沙漏，读完没有损失。
]

#story-box(from: "s5s_20", pick: ("去中庭",), noskip: ("s5s_140", "s5s_320", "s5s_580"))[
  从 #card("Sakura同学") 接着讲 #arrow #card("章节 5：Sakura") #arrow #card("Sakura的日记：9月13日")（传闻是指？选 #opt("下雪")，另两项会绕回）#arrow #card("Sakura的日记：7月（未写完）")（去哪里？选 #opt("去中庭")）#arrow #card("中庭的Ayano同学")：首次未持卡耗时 100，#timeover
]
#frag-box[
  #make-cards(("中庭的Ayano同学", [依次递 #card("Sakura的日记：9月13日")、#card("Sakura的日记：7月（未写完）")]))
]

回到故事模式从 #card("中庭的Ayano同学") 接着讲。下表是每个场景结束时彩野的提问要点和该递的卡。递卡界面无法取消，递错的代价分两种：

#warn-box(title: "递错的代价")[
  只递一张的日记递错不会 Game Over，但沙漏立即涨一截再问一遍：9月13日、7月、中庭这三篇涨 30，9月16日、9月16日（夜）、9月20日涨 40，9月23日起各篇涨 50。这个沙漏在本章各篇之间是累计的，涨满 100 就 Time over——50 的那几篇错两次就到顶；要清掉已涨的沙漏，得从时间轴回到出错那篇*之前*重讲。9月22日（连递三张）与 2月13日（连递十一张）则是一错即 #gameover，提示「仔细听她的话，慎重选卡」，从时间轴回到那篇重讲即可（已持卡，零耗时），但十一张要从头再递。
]

#set par(first-line-indent: 0em)
#table(
  columns: (1.1fr, 1fr, 1.4fr),
  stroke: 0.4pt + c-line, inset: (x: 7pt, y: 4.5pt),
  fill: (x, y) => if y == 0 { c-soft } else { none },
  table.header([*场景*], [*选项*], [*场景结束时递出的卡*]),
  [#card("章节 5：Sakura") → #card("Sakura的日记：9月13日")], [传闻是指？选 #opt("下雪")，另两项会绕回], [#card("Sakura的日记：7月（未写完）")],
  [#card("Sakura的日记：7月（未写完）")], [去哪里？选 #opt("去中庭")], [进入 #card("中庭的Ayano同学")；首次会因未持卡耗时 100],
  [#card("中庭的Ayano同学")], [—], [#card("Sakura的日记：9月16日")],
  [#card("Sakura的日记：9月16日")], [—], [#card("Sakura的日记：9月16日（夜）")],
  [#card("Sakura的日记：9月16日（夜）")], [发作：选 #opt("不硬撑")。只有本轮去过中庭才有此项，否则只剩 #opt("试着撑一下") 且是 #gameover], [#card("Sakura的日记：9月20日")],
  [#card("Sakura的日记：9月20日")], [—], [#card("Sakura的日记：9月22日")],
  [#card("Sakura的日记：9月22日")], [—], [依次 #card("Sakura的日记：9月13日")、#card("Sakura的日记：9月16日")、#card("Sakura的日记：9月23日")],
  [#card("Sakura的日记：9月23日")], [—], [#card("Sakura的日记：9月29日")],
  [#card("Sakura的日记：9月29日")], [—], [#card("Sakura的日记：断片")],
  [#card("Sakura的日记：断片")], [出现关键词卡 #card("自我暗示")、#card("强迫观念")、#card("冬天的告白会失败")], [#card("Sakura的日记：10月3日")],
  [#card("Sakura的日记：10月3日")], [—], [#card("Sakura的日记：11月12日")],
  [#card("Sakura的日记：11月12日")], [持 #card("章节 EX1") 后多出「他的身影」选择，此时选 #opt("回家")], [#card("Sakura的日记：2月13日")],
  [#card("Sakura的日记：2月13日")], [—], [依次 #card("Sakura的日记：9月13日")、#card("中庭的Ayano同学")、#card("Sakura的日记：9月16日")、#card("Sakura的日记：9月16日（夜）")、#card("Sakura的日记：9月20日")、#card("Sakura的日记：9月22日")、#card("Sakura的日记：9月23日")、#card("Sakura的日记：9月29日")、#card("Sakura的日记：断片")、#card("Sakura的日记：10月3日")、#card("Sakura的日记：11月12日")],
)
#set par(first-line-indent: (amount: 2em, all: true))

== 章节 5 完成

#story-box(from: "s5s_200", pick: ("不硬撑",), noskip: ("s5s_140", "s5s_320", "s5s_580"))[
  从 #card("中庭的Ayano同学") 接着讲，按上表一路递卡（发作时选 #opt("不硬撑")）#arrow #card("Sakura的日记：2月13日") 的递卡全部正确 #arrow #card("章节 5：Ayano") #arrow #card("Ayano的回信：9月25日") #arrow #card("Ayano的回信：10月30日") #arrow #card("2月，中庭") #arrow #complete
]
#frag-box[
  #make-cards(("2月，中庭", [章节终卡 #cn(193)。依次递 #card("Sakura的日记：9月13日")、#card("中庭的Ayano同学")、#card("Ayano的回信：9月25日")]))
]

现实层「章节 5 读完」：傍晚的教室、彩野家的晚饭与扑克牌、老板给的威士忌、彩野的笔记本、9 月的信。获得 #card("章节 5 梗概") #cn(139)。
