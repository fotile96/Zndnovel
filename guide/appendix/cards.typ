#import "../template.typ": *
#import "../generated/cards-table.typ": cards-rows

= 卡片一览（195 张）

#set par(first-line-indent: 0em)
按卡号排列。「格位」是这张卡在选卡界面 15 列 × 13 行网格里的位置与该格的样子（总览图见第 1 章）；「前置卡」是开始做卡前必须已持有的卡，缺卡时彩野会说这段记不起来；「递出的卡」是做卡时要从手牌里交给彩野的卡（多张时按表内顺序）；「无需递卡」表示只要前置条件满足、进入片段模式选中场景就自动做成。关键词卡在故事模式听完对应场景后自动进手牌。

#set text(size: 8.4pt)
#table(
  columns: (2.0em, 7.3em, 4.0em, 1fr, 1fr, 1.1fr, 1.1fr, 4.0em),
  stroke: 0.35pt + c-line,
  inset: (x: 4pt, y: 3pt),
  align: (x, y) => if x == 1 { horizon + left } else { top + left },
  fill: (x, y) => if y == 0 { c-soft } else if calc.odd(y) { rgb("#FAFBFC") } else { none },
  table.header(
    [*号*], [*格位*], [*分类*], [*日文卡名*], [*中文卡名*], [*前置卡*], [*递出的卡*], [*入手*],
  ),
  ..cards-rows.map(r => (
    text(r.at(0)),
    box[#cell-swatch(int(r.at(0))) #h(0.2em) #text(size: 0.9em, fill: c-gray, r.at(1))],
    ..r.slice(2).map(x => text(x)),
  )).flatten()
)
