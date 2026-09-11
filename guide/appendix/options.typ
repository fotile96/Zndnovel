#import "../template.typ": *
#import "../generated/options-table.typ": option-groups

= 选项文字对照（134 个按钮）

#set par(first-line-indent: 0em)
按出现的选择场景分组，字母为按钮编号（`sel_<场景>_<字母>`），日文为原版按钮烤字，中文为中文化版按钮烤字。正文里所有「选项」均引用此处的中文。

#set text(size: 9pt)
#for g in option-groups [
  #block(above: 0.9em, below: 0.3em, text(font: f-sans, weight: "bold", size: 9.5pt, fill: c-accent)[#g.at(0)])
  #table(
    columns: (1.6em, 1fr, 1fr),
    stroke: 0.35pt + c-line,
    inset: (x: 5pt, y: 3pt),
    ..g.at(1).map(r => (text(font: f-sans, fill: c-gray, r.at(0)), text(r.at(1)), text(r.at(2)))).flatten()
  )
]
