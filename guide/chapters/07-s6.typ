#import "../template.typ": *

= 章节 6：True Color

#chapter-open(entry: [章节 3 的 #card("选择：颇有意思的传闻") 选 #opt("不听")], unlock: [持有 #card("章节 5 梗概")])[
  Sakura 寄来一封信，指向图书室里两人合写的笔记本。本章的两张大卡 #card("选择：笔记本") 与 #card("True Color") 分别要递十张与十四张卡，是全作最长的做卡流程。
]

== 进入章节 6

#story-box(from: "s1s_35_sel", pick: ("没有约", "不去", "不知道", "告诉我", "没兴趣"))[
  时间轴停在章节 5，先把它讲回章节 3，让『选择：颇有意思的传闻』回到时间轴上：#card("选择：放学后的约定") 选 #opt("没有约") #arrow #card("夏天的计划") #arrow #card("选择：周末的计划") 选 #opt("不去") #arrow #card("午休的走廊") #arrow #card("选择：楼梯的传闻") 选 #opt("不知道") #arrow #card("选择：颇有意思的传闻") 选 #opt("告诉我") #arrow #card("选择：传闻是指") 选 #opt("没兴趣") #arrow #card("对传闻没兴趣") #arrow #gameover。除『选择：颇有意思的传闻』花 25 以外全部持卡跳过。
]
#frag-box[
  #make-cards(("选择：颇有意思的传闻", [递 #card("章节 5 梗概")。做成后出现 #opt("不听")]))
]
#story-box(from: "s3s_50_sel", pick: ("不听", "在家读"))[
  回到 #card("选择：颇有意思的传闻") 选 #opt("不听") #arrow #card("有冲击力的传闻") #arrow #card("章节 6：Ayano") #arrow #card("选择：在哪里读")：默认只有 #opt("在家读") #arrow #card("Sakura的来信") #timeover #deadend
]
#frag-box[
  #make-cards(
    ("有冲击力的传闻", [无需递卡]),
    ("章节 6：Ayano", [需先持有 #card("有冲击力的传闻")；无需递卡]),
    ("Sakura的来信", [无需递卡]),
    ("选择：在哪里读", [递 #card("Sakura的来信")。做成后出现 #opt("在图书室读")]),
  )
]

== 图书室的笔记本

#story-box(from: "s6s_60_sel", pick: ("在图书室读",))[
  #card("选择：在哪里读") 选 #opt("在图书室读") #arrow #card("在图书室读")：耗时 100，#timeover
]
#frag-box[
  #make-cards(("在图书室读", [做卡剧情里要给三个人物排座次，六选一，正确答案是 #opt("A.Ayano B.Sakura C.Yuichi")]))
]
#story-box(from: "s6s_110", pick: ("已失去的梦之物语",))[
  从 #card("在图书室读") 接着讲 #arrow #card("选择：笔记本")：默认只有 #opt("已失去的梦之物语") #arrow #card("已失去的梦之物语") #arrow #gameover
]
#frag-box[
  #make-cards(
    ("已失去的梦之物语", [无需递卡]),
    ("选择：笔记本", [大谜题 #cn(103)。依次递 #card("已失去的梦之物语")、#card("章节 1 梗概")、#card("章节 2 梗概")、#card("章节 3A 梗概")、#card("章节 3B 梗概")、#card("章节 4A 梗概")、#card("章节 4B 梗概")、#card("章节 5 梗概")、#card("总有一天你会看到的故事。")、#card("口袋里的字条")。做成后出现 #opt("True Color")]),
  )
]

#story-box(from: "s6s_150_sel", pick: ("True Color",))[
  #card("选择：笔记本") 选 #opt("True Color") #arrow #card("True Color") #arrow #card("选择：天台的归途")：耗时 100，选项弹出前 #timeover
]
#frag-box[
  #make-cards(
    ("True Color", [大谜题 #cn(104)。按日期依次递 #card("Sakura的日记：9月13日")、#card("Sakura的日记：7月（未写完）")、#card("Sakura的日记：9月16日")、#card("Sakura的日记：9月16日（夜）")、#card("Sakura的日记：9月20日")、#card("Sakura的日记：9月22日")、#card("Sakura的日记：9月23日")、#card("Sakura的日记：9月29日")、#card("Sakura的日记：断片")、#card("Sakura的日记：10月3日")、#card("Sakura的日记：11月12日")、#card("Sakura的日记：2月13日")，然后 #card("Ayano的回信：9月25日")、#card("Ayano的回信：10月30日")]),
    ("选择：天台的归途", [需先持有 #card("True Color")；递 #card("有个女孩子来学校的故事")。做成后出现 #opt("中庭的雪")]),
  )
]

== 章节 6 完成

#story-box(from: "s6s_280_sel", pick: ("中庭的雪",))[
  #card("选择：天台的归途") 选 #opt("中庭的雪")（#opt("还在这里") 是一个没有卡的 Game Over，不必走）#arrow #card("中庭的雪") #arrow #complete
]
#frag-box[
  #make-cards(("中庭的雪", [章节终卡 #cn(110)。依次递 #card("有冲击力的传闻")、#card("在图书室读")、#card("True Color")、#card("Sakura")]))
]

现实层「章节 6 读完」：Sakura 的日记、Yuichi 的口信、睡着的两人、Yuichi 的遗书、你的温柔之处。获得 #card("章节 6 梗概") #cn(140)。彩野的故事到此讲完，主菜单出现 Section 7。
