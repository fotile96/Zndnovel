#import "../template.typ": *

= 序章与章节 1

#chapter-open(entry: [主菜单 Prologue → Story], unlock: [无])[
  序章是纯现实层的引子。章节 1 是教学章：三选一的放学后约定、Yuichi 的答卷、放学后的钱仙，以及第一次从天台坠落。本章结束时你会掌握「Game Over → 做卡 → 解锁选项 → 重讲」这一整套循环。
]

== 序章

主菜单选 Prologue。六个场景一路看完（想忘记的记忆、前往校内、走在走廊上、彩野同学的记忆、我们的教室），直哉在教室里与彩野重逢。序章读完自动获得 #card("有个女孩子来学校的故事") #cn(1)，主菜单变为 Story。

== 教程

#story-box[
  片头 #arrow #card("夏日清晨，通往高中的上学路")。这一场固定耗时 100，讲完沙漏直接满，进入片段模式教程。
]
#frag-box[
  按提示做出第一张卡。做完播放 OP 动画，主菜单从此出现 Fragment。
  #make-cards(("夏日清晨，通往高中的上学路", [递 #card("有个女孩子来学校的故事")]))
]

== 第一轮：放学后的约定

#story-box[
  #card("放学后的约定")（自动入手 #card("汉堡")、#card("黑板上方的时钟")）#arrow #card("选择：放学后的约定")：此时只有 #opt("想不起约定") 可选 #arrow #card("想不起约定")（入手 #card("小菊")）#arrow #card("想起约定")（入手 #card("和那个女孩见面的约定")）#arrow #card("早晨的教室")（入手 #card("夫妻吵架")）#arrow #card("章节 1：Ayano") #arrow #card("午休的教室")，耗时 100，#timeover。
]
#frag-box[
  #make-cards(
    ("放学后的约定", [递 #card("汉堡")]),
    ("选择：放学后的约定", [递 #card("和那个女孩见面的约定")。做成后该场景出现 #opt("约好了") 与 #opt("没有约")]),
  )
]

#story-box[
  回到 #card("选择：放学后的约定") 选 #opt("约好了") #arrow #card("约好了")（入手 #card("橡皮")）#arrow #card("早晨的教室") #arrow #card("章节 1：Ayano") #arrow #card("午休的教室")（入手 #card("Yukari老师")）。
]
#frag-box[
  #make-cards(
    ("约好了", [递 #card("小菊")]),
    ("早晨的教室", [递 #card("黑板上方的时钟")]),
    ("章节 1：Ayano", [递 #card("早晨的教室")。做成后额外获得关键词卡 #card("故事的主人公")]),
  )
]

#story-box[
  再回到分歧点，分别走一遍 #opt("没有约") 与 #opt("想不起约定")。#opt("没有约") 在没有 #card("章节 1 梗概") 时会接回 #card("想起约定")；这两条支线都只是为了把场景讲出来好做卡。
]
#frag-box[
  #make-cards(
    ("没有约", [递 #card("橡皮")]),
    ("想起约定", [递 #card("夫妻吵架")]),
    ("想不起约定", [递 #card("没有约")]),
    ("午休的教室", [递 #card("想不起约定")]),
  )
]

== 第二轮：Yuichi 的答卷

#story-box[
  #card("午休的教室") #arrow #card("选择：Yuichi的答卷")：默认只有 #opt("岔开答卷的话题") #arrow #card("岔开答卷的话题") #arrow #card("开始上课") #arrow #card("放学后") #arrow 因为这一轮没讲过「羡慕」，进入 #card("探索：放学后的学校")。探索先不用做完，沙漏满了就回片段模式。
]
#frag-box[
  #make-cards(
    ("岔开答卷的话题", [递 #card("章节 1：Ayano")]),
    ("开始上课", [递 #card("Yukari老师")]),
    ("放学后", [递 #card("早晨的教室")]),
    ("选择：Yuichi的答卷", [递 #card("岔开答卷的话题")。做成后出现 #opt("对答卷表示羡慕")]),
  )
]

#story-box[
  选 #opt("对答卷表示羡慕") #arrow #card("对答卷表示羡慕") #arrow #card("开始上课") #arrow #card("放学后") #arrow 这一轮讲过「羡慕」，Ayano 去了快餐店：#card("Yuichi与快餐")（入手 #card("Yuichi")）#arrow #card("选择：回学校")：默认只有 #opt("回学校") #arrow #card("放学后的钱仙")（入手 #card("钱仙")）#arrow 往下讲到沙漏满。
]
#frag-box[
  #make-cards(
    ("对答卷表示羡慕", [递 #card("汉堡")]),
    ("Yuichi与快餐", [递 #card("对答卷表示羡慕")]),
    ("放学后的钱仙", [递 #card("钱仙")]),
  )
]

== 第三轮：探索放学后的学校，以及第一个 Game Over

#story-box[
  回到 #card("选择：Yuichi的答卷") 选 #opt("岔开答卷的话题")，走到 #card("探索：放学后的学校")。地图上有教室、走廊、天台、中庭、操场五个点，*每个点各去两次*（第三次只会重复），五个点都到过两次后探索自动结束，入手 #card("总是马上就回家") 与 #card("天台", id: 119)。之后 #card("放学后的钱仙") #arrow #card("与她的相遇") #arrow #card("不好的结果")（入手 #card("将来的职业")）#arrow #card("回过神来的地方")（入手 #card("回过神来已在天台")）#arrow #card("选择：声音的主人")：默认只有 #opt("……") #arrow #card("她的名字")（入手 #card("Sakura")）#arrow 这一轮没有「羡慕」，Yuichi 不在场：#card("约定不守可不行")（入手 #card("从天台坠落")）#arrow #gameover
]
#frag-box[
  #make-cards(
    ("探索：放学后的学校", [卡 20。递 #card("天台", id: 119)], 20),
    ("与她的相遇", [递 #card("和那个女孩见面的约定")]),
    ("不好的结果", [需先持有卡 20；递 #card("将来的职业")]),
    ("回过神来的地方", [递 #card("回过神来已在天台")]),
    ("她的名字", [递 #card("Sakura")]),
    ("约定不守可不行", [递 #card("Sakura")]),
  )
]

#tip-box(title: "Game Over 提示")[
  这个 Game Over 的画面提示是「好好接住 Yuichi 的答卷」：只有本轮讲过 #card("对答卷表示羡慕")，Yuichi 才会出现在天台救人。
]

== 第四轮：章节 1 完成

#story-box[
  #card("选择：Yuichi的答卷") 选 #opt("对答卷表示羡慕") #arrow #card("Yuichi与快餐") #arrow #card("选择：回学校") 选 #opt("回学校") #arrow #card("放学后的钱仙") #arrow … #arrow #card("选择：声音的主人") 选 #opt("……") #arrow #card("她的名字") #arrow #card("Yuichi救下Ayano") #arrow #card("有谁在呼唤") #arrow #complete
]
#frag-box[
  #make-cards(
    ("Yuichi救下Ayano", [递 #card("Yuichi")]),
    ("选择：回学校", [递 #card("从天台坠落")。做成后出现 #opt("回家")]),
  )
]
#story-box[
  回到 #card("选择：回学校") 选 #opt("回家") #arrow #card("一如往常的生活") #arrow #gameover
]
#frag-box[
  #make-cards(
    ("一如往常的生活", [递 #card("总是马上就回家")]),
    ("有谁在呼唤", [章节终卡 #cn(30)。依次递 #card("有个女孩子来学校的故事")、#card("夏日清晨，通往高中的上学路")、#card("章节 1：Ayano")、#card("放学后的钱仙")、#card("一如往常的生活")、#card("约定不守可不行")、#card("Yuichi救下Ayano")]),
  )
]

做成 #card("有谁在呼唤") 后进入现实层剧本「章节 1 读完」：直哉送彩野回家，从彩野母亲那里得知 Sakura 是真实存在过的人，并在学校见到自称 Sakura 妹妹的千秋。看完获得 #card("章节 1 梗概") #cn(133)，回想与文库第 3 本解锁。

#warn-box(title: "章节 1 的两个隐藏分歧先别管")[
  #card("选择：声音的主人") 的 #opt("Sakura同学") 与 #card("选择：放学后的约定") 的 #opt("没有约") 在持有相应门控卡之后分别通往章节 5 与章节 2，见后文。
]
