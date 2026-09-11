#import "../template.typ": *

= 完全收集

#chapter-open(entry: [—], unlock: [—])[
  195 张卡、13 种 Game Over、4 个故事层结局、回想与三个画廊。本章是核对清单，卡片明细见附录 A。
]

== 卡片构成

#set par(first-line-indent: 0em)
#table(
  columns: (1fr, auto, 2fr),
  stroke: 0.4pt + c-line, inset: (x: 7pt, y: 4.5pt),
  fill: (x, y) => if y == 0 { c-soft } else { none },
  table.header([*分类*], [*张数*], [*入手*]),
  [场景梗概卡（含探索）], [122], [片段模式做卡],
  [选择卡], [36], [片段模式做卡，做成后解锁该场景的全部选项],
  [关键词卡], [38], [故事模式听完场景自动入手；#card("故事的主人公")、#card("绝对灵验的咒语")、#card("Ayano") 由做卡附带获得],
  [章节梗概卡], [13], [各章现实层剧本看完获得（含 #card("总有一天你会看到的故事。")）],
  [日记卡], [16], [做成 #card("Sakura同学") 时一次性获得],
)
#set par(first-line-indent: (amount: 2em, all: true))

按卡号顺序在图鉴里补空时，最常见的漏卡是各条 Game Over 支线的场景卡。下表列出全部 Game Over 及其对应的卡。

== Game Over 一览

#set par(first-line-indent: 0em)
#table(
  columns: (auto, 1.3fr, 1.7fr),
  stroke: 0.4pt + c-line, inset: (x: 7pt, y: 4.5pt),
  fill: (x, y) => if y == 0 { c-soft } else { none },
  table.header([*章*], [*结局场景*], [*到达方式*]),
  [1], [#card("一如往常的生活")], [#card("选择：回学校") 选 #opt("回家")],
  [1], [#card("约定不守可不行")], [本轮未讲 #card("对答卷表示羡慕") 时走到 #card("她的名字")],
  [2], [#card("又是一如往常的生活")], [未持 #card("章节 2 梗概") 时，#opt("不去") 或咒语兴趣的前三项],
  [2], [#card("回荡在走廊的声音")], [讲过 #card("喜欢Yuichi")，但咒语不是「橡皮＋绝对灵验」],
  [2], [#card("Yuichi的背影")], [讲过 #card("对Yuichi嘛……")，且咒语不是「橡皮＋绝对灵验」],
  [3], [#card("对传闻没兴趣")], [#card("选择：传闻是指") 选 #opt("没兴趣") 或 #opt("不知道")],
  [3], [#card("天台", id: 85) #cn(85)], [本轮讲过 #card("亲吻")，之后走到楼梯],
  [4], [#card("走廊上的Yuichi")], [#card("选择：看到字条时") 选 #opt("没有兴趣") 并完成探索],
  [4], [#card("天台的人影")], [字条选 #opt("真无聊")，或课桌／笔记本选择里选 #opt("天台的人影")、#opt("寻找Ayano")],
  [4], [#card("抓住手臂")], [#card("选择：将Ayano――") 选 #opt("抓住手臂")],
  [5], [—], [发作时选 #opt("试着撑一下")；任何一次递错日记卡],
  [6], [#card("Sakura的来信")], [#card("选择：在哪里读") 选 #opt("在家读")],
  [6], [#card("已失去的梦之物语")], [#card("选择：笔记本") 选 #opt("已失去的梦之物语")],
  [6], [—], [#card("选择：天台的归途") 选 #opt("还在这里")],
)
#set par(first-line-indent: (amount: 2em, all: true))

== 故事层结局

- 章节 3A #card("与Yuichi接吻") 与 3B #card("不与Yuichi接吻")。
- 章节 4A #card("消失的Sakura") 与 4B #card("等Sakura")。
- 章节 1、2、5、6、8、EX1、EX2 各一个完成结局。

== 回想、文库、音乐、CG

- *回想*：序章由 #card("有个女孩子来学校的故事") 解锁，其余按 #card("章节 1 梗概") 至 #card("章节 EX2") 逐章解锁，强制事件由 #card("总有一天你会看到的故事。") 解锁。
- *文库*：第 1 至 5 本分别由 #card("章节 2 梗概")、#card("章节 4A 梗概")、#card("章节 1 梗概")、#card("章节 3A 梗概")、#card("章节 4B 梗概") 解锁。文库页图为日文原版，中文版未汉化。
- *音乐*：#card("章节 7 梗概")。
- *CG*：剧情中看过即登录，全部章节读完即 100%。
