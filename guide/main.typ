// main.typ —— 封面 / 目录 / 章节 include。编译：uv run python tools/build_guide.py
#import "template.typ": *
#show: project

// ------------------------------- 封面 --------------------------------
#page(header: none, footer: none)[
  #v(4.2cm)
  #align(center)[
    #text(font: f-sans, size: 12pt, fill: c-gray, tracking: 0.3em)[PSP · 日本一ソフトウェア · 2010]
    #v(1.0cm)
    #text(font: f-sans, size: 26pt, weight: "bold", fill: c-accent)[セカンドノベル]
    #v(0.25cm)
    #text(font: f-sans, size: 15pt, fill: c-ink)[〜彼女の夏、15分の記憶〜]
    #v(0.9cm)
    #line(length: 6cm, stroke: 1pt + c-accent)
    #v(0.9cm)
    #text(font: f-sans, size: 20pt, weight: "bold")[中文攻略]
    #v(0.4cm)
    #text(size: 11pt, fill: c-gray)[全章节流程 · 分歧与门控 · 卡片收集 · 附录：卡名与选项定译对照]
    #v(3.5cm)
    #block(width: 74%)[
      #set par(first-line-indent: 0em, justify: true)
      #set text(size: 9.5pt, fill: c-gray)
      流程骨架参考 makapy 的『プレイ日記＆攻略』连载（2010 年 8 月，共 15 篇），
      分歧条件、门控卡与探索完成条件按游戏脚本调度器（`data/dag.json`）核对补齐。
      卡名与选项文字采用中文化版的烤字定译，与游戏内显示逐字一致。
    ]
  ]
]

// ------------------------------- 目录 --------------------------------
#page(header: none)[
  #text(font: f-sans, size: 18pt, weight: "bold")[目录]
  #v(0.6cm)
  #set par(first-line-indent: 0em)
  #show outline.entry.where(level: 1): it => { v(0.55em, weak: true); strong(it) }
  #outline(title: none, depth: 2, indent: 1.2em)
]

#set page(numbering: "1")
#counter(page).update(1)

#include "chapters/00-howto.typ"
#include "chapters/01-prologue-s1.typ"
#include "chapters/02-s2.typ"
#include "chapters/03-s3.typ"
#include "chapters/04-s4.typ"
#include "chapters/05-s3b-s3fc.typ"
#include "chapters/06-s5.typ"
#include "chapters/07-s6.typ"
#include "chapters/08-s7-s8.typ"
#include "chapters/09-ex.typ"
#include "chapters/10-completion.typ"

// ------------------------------- 附录 --------------------------------
#counter(heading).update(0)
#set heading(numbering: (..nums) => {
  let n = nums.pos()
  let letters = ("A", "B", "C")
  if n.len() == 1 [附录#letters.at(n.at(0) - 1)] else [#letters.at(n.at(0) - 1).#n.slice(1).map(str).join(".")]
})
#include "appendix/cards.typ"
#include "appendix/options.typ"
