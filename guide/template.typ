// =====================================================================
// template.typ ——《セカンドノベル》中文攻略 · 排版模板
// 源自 ~/tut/book-project-starter 的 A4 中文模板，裁掉读书讲义专用构件，
// 加上攻略专用构件：card()/opt() 定译断言、路线框、做卡表、分歧表、Game Over 标注。
// 字体缺失时 Typst 不报错只画方块，故一律写回退列表。
// =====================================================================
#import "generated/data.typ": card-titles, option-texts, scene-titles, card-pos

#let f-serif = ("Noto Serif CJK SC", "Songti SC")
#let f-sans  = ("Noto Sans CJK SC", "PingFang SC")
#let f-mono  = ("Noto Sans Mono CJK SC", "Menlo")

#let c-ink    = rgb("#232323")
#let c-accent = rgb("#1F4E79")   // 藏蓝：标题与强调（呼应游戏的夏日教室蓝调）
#let c-soft   = rgb("#EEF3F8")   // 浅蓝灰：路线框
#let c-note   = rgb("#F5EFE6")   // 米色：提示框
#let c-warn   = rgb("#F7ECEA")   // 浅红：Game Over / 注意
#let c-line   = rgb("#B9C4CF")
#let c-gray   = rgb("#6B6B6B")
#let c-card   = rgb("#7A2E24")   // 卡名色
#let c-opt    = rgb("#1F4E79")   // 选项色

// ---------------------------------------------------------------------
// 定译引用：名字不在定译集合里 → 编译失败（这是刻意的）
// 选卡界面格位：小色块（该格在光标下的样子）+「r行c列」
#let cell-swatch(id) = box(baseline: 24%, stroke: 0.3pt + c-line, clip: true, image("generated/cells/c" + (
  if id < 10 { "00" } else if id < 100 { "0" } else { "" }) + str(id) + ".png", height: 0.9em))
#let cell-pos(id) = {
  let p = card-pos.at(str(id))
  box(text(font: f-sans, size: 0.72em, fill: c-gray)[#p.at(0)行#p.at(1)列])   // box：不许在数字与「行/列」之间折行
}
// 卡名。同名卡（『探索：放学后的学校』20/74、『天台』85/119）用 id: 指定；pos: false 只出名字
#let card(name, id: none, pos: true) = {
  assert(card-titles.at(name, default: none) != none,
    message: "未知卡名（不在 skeleton/cards.zh.yaml 定译里）: " + name)
  let n = if id != none { id } else { card-titles.at(name) }
  text(fill: c-card)[『#name』]
  if pos [#h(0.1em)#box[#cell-swatch(n)#h(0.12em)#cell-pos(n)]]
}
#let opt(name) = {
  assert(option-texts.at(name, default: none) != none,
    message: "未知选项文本（不在选项烤字定译里）: " + name)
  text(fill: c-opt, font: f-sans, size: 0.95em)[「#name」]
}
// 场景名（场景标题定译；多数与卡名同名，个别只有场景没有卡）
#let scn(name) = {
  assert(scene-titles.at(name, default: none) != none,
    message: "未知场景标题（不在 data/extra_translated.jsonl 定译里）: " + name)
  text(fill: c-gray)[〈#name〉]
}
// 卡号引用
#let cn(n) = text(font: f-sans, size: 0.85em, fill: c-gray)[（卡#n）]

// ---------------------------------------------------------------------
// 模式标签：★故事模式 / ★片段模式（沿用博客的 ★Story / ★Fragment 记法）
#let story = text(font: f-sans, weight: "bold", fill: c-accent)[★ 故事模式]
#let frag  = text(font: f-sans, weight: "bold", fill: c-card)[★ 片段模式]
#let gameover = box(fill: c-warn, inset: (x: 4pt, y: 1.5pt), radius: 2pt,
  text(font: f-sans, size: 0.85em, fill: rgb("#7A2E24"), weight: "bold")[GAME OVER])
#let timeover = box(fill: c-warn, inset: (x: 4pt, y: 1.5pt), radius: 2pt,
  text(font: f-sans, size: 0.85em, fill: rgb("#7A2E24"), weight: "bold")[TIME OVER])
#let complete = box(fill: c-soft, inset: (x: 4pt, y: 1.5pt), radius: 2pt,
  text(font: f-sans, size: 0.85em, fill: c-accent, weight: "bold")[章节完成])
#let arrow = sym.arrow.r

// 路线框：一段「故事模式」或「片段模式」的操作序列
#let route-box(title, body) = block(
  width: 100%, fill: c-soft, stroke: (left: 2.5pt + c-accent),
  inset: (x: 12pt, y: 9pt), radius: 2pt, above: 1.0em, below: 1.0em,
)[
  #set par(first-line-indent: 0em)
  #title
  #v(3pt)
  #set text(size: 0.95em)
  #body
]

// 做卡表：每行 (目标卡, 递出的答案卡或说明)
#let make-cards(..rows) = {
  set par(first-line-indent: 0em)
  table(
    columns: (1fr, 1.2fr),
    stroke: 0.4pt + c-line,
    inset: (x: 7pt, y: 4.5pt),
    fill: (x, y) => if y == 0 { c-soft } else { none },
    table.header(
      text(font: f-sans, weight: "bold", size: 0.9em)[要做的卡],
      text(font: f-sans, weight: "bold", size: 0.9em)[递给彩野的卡 / 条件],
    ),
    ..rows.pos().map(r => (
      text(size: 0.95em, card(r.at(0), id: if r.len() > 2 { r.at(2) } else { none })),
      text(size: 0.95em, r.at(1)),
    )).flatten()
  )
}

// 分歧表：每行 (选项, 去向说明)
#let branches(..rows) = {
  set par(first-line-indent: 0em)
  table(
    columns: (1fr, 2fr),
    stroke: 0.4pt + c-line,
    inset: (x: 7pt, y: 4.5pt),
    ..rows.pos().map(r => (text(size: 0.95em, opt(r.at(0))), text(size: 0.95em, r.at(1)))).flatten()
  )
}

// 提示框
#let tip-box(title: "提示", body) = block(
  width: 100%, fill: c-note, inset: (x: 12pt, y: 9pt), radius: 3pt,
  above: 1.0em, below: 1.0em,
)[
  #set par(first-line-indent: 0em)
  #text(font: f-sans, weight: "bold", size: 0.88em, fill: rgb("#8C5A1B"))[◇ #title]
  #h(0.6em)
  #text(size: 0.95em)[#body]
]

// 注意框
#let warn-box(title: "注意", body) = block(
  width: 100%, fill: c-warn, stroke: (left: 2.5pt + rgb("#A94A3F")),
  inset: (x: 12pt, y: 9pt), radius: 2pt, above: 1.0em, below: 1.0em,
)[
  #set par(first-line-indent: 0em)
  #text(font: f-sans, weight: "bold", size: 0.88em, fill: rgb("#7A2E24"))[◆ #title]
  #v(3pt)
  #text(size: 0.95em)[#body]
]

// 章首导航条
#let chapter-open(entry: none, unlock: none, body) = {
  block(width: 100%, inset: (x: 0pt, y: 2pt), above: 0.6em, below: 1.4em)[
    #set par(first-line-indent: 0em)
    #line(length: 100%, stroke: 0.5pt + c-line)
    #v(5pt)
    #text(font: f-sans, size: 0.85em, fill: c-gray)[
      #if entry != none [*入口* #entry]
      #if unlock != none [ #h(1em) *解锁条件* #unlock]
    ]
    #v(2pt)
    #text(size: 0.95em, style: "italic")[#body]
    #v(5pt)
    #line(length: 100%, stroke: 0.5pt + c-line)
  ]
}

// ---------------------------------------------------------------------
// 全局样式
#let project(body) = {
  set document(title: "セカンドノベル 〜彼女の夏、15分の記憶〜 中文攻略", author: "Zndnovel 汉化组")
  set page(
    paper: "a4",
    margin: (top: 2.4cm, bottom: 2.5cm, left: 2.3cm, right: 2.3cm),
    header: context {
      // 章首页的一级标题在页眉之后才出现，先看本页有没有新章，再退回上一章
      let pg = here().page()
      let on-page = query(heading.where(level: 1).after(here())).filter(h => h.location().page() == pg)
      let before = query(heading.where(level: 1).before(here()))
      let h = if on-page.len() > 0 { on-page.first() } else if before.len() > 0 { before.last() } else { none }
      if h != none and counter(page).get().first() > 1 {
        set text(font: f-sans, size: 8pt, fill: c-gray)
        grid(columns: (1fr, auto),
          align(left)[セカンドノベル 中文攻略],
          align(right)[#h.body])
        v(-4pt)
        line(length: 100%, stroke: 0.4pt + c-line)
      }
    },
    footer: context {
      let n = if page.numbering != none { page.numbering } else { "1" }
      align(center)[
        #set text(font: f-sans, size: 9pt, fill: c-gray)
        #counter(page).display(n)
      ]
    },
  )
  set text(font: f-serif, size: 10.5pt, fill: c-ink, lang: "zh", region: "cn")
  set par(justify: true, leading: 0.82em, spacing: 1.0em,
    first-line-indent: (amount: 2em, all: true))
  set heading(numbering: (..nums) => {
    let n = nums.pos()
    if n.len() == 1 [第#str(n.at(0))章] else [#n.map(str).join(".")]
  })
  show heading: set text(font: f-sans, fill: c-ink)
  show heading.where(level: 1): it => {
    pagebreak(weak: true)
    v(1.0cm)
    if it.numbering != none {
      text(font: f-sans, size: 13pt, fill: c-accent, weight: "medium")[
        #counter(heading).display(it.numbering)
      ]
      v(0.15cm)
    }
    text(font: f-sans, size: 21pt, weight: "bold")[#it.body]
    v(0.5cm)
  }
  show heading.where(level: 2): it => {
    block(above: 1.6em, below: 0.9em)[
      #text(size: 13.5pt, weight: "bold")[
        #if it.numbering != none [#counter(heading).display(it.numbering)#h(0.5em)]
        #it.body
      ]
    ]
  }
  show heading.where(level: 3): it => {
    block(above: 1.3em, below: 0.7em)[
      #text(size: 11.5pt, weight: "bold")[
        #if it.numbering != none [#counter(heading).display(it.numbering)#h(0.5em)]
        #it.body
      ]
    ]
  }
  show table: set text(size: 0.95em)
  show table.cell: set par(first-line-indent: 0em)
  show figure.caption: it => { set text(size: 0.86em, fill: c-gray); set par(first-line-indent: 0em); it }
  show raw.where(block: false): set text(font: f-mono, size: 0.92em)
  show raw.where(block: true): it => block(width: 100%, fill: rgb("#F6F4EF"), inset: 9pt, radius: 3pt,
    text(font: f-mono, size: 0.88em, it))
  show link: set text(fill: rgb("#33556B"))
  set list(indent: 1.1em, spacing: 0.7em)
  set enum(indent: 1.1em, spacing: 0.7em)
  body
}
