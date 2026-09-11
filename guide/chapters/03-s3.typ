#import "../template.typ": *

= 章节 3A：闹鬼楼梯

#chapter-open(entry: [章节 2 的 #opt("不去") 或 #opt("没什么特别的")], unlock: [持有 #card("章节 2 梗概")])[
  没有约定也没有咒语的第三个夏天：Ayano 去追查「闹鬼楼梯」的传闻。本章有一段带顺序要求的校内探索，以及在图书室目击 Yuichi 与 Yukari 老师接吻这个反复出现的 Game Over。
]

== 进入章节 3

章节 2 里任何回到「又是一如往常的生活」的分歧，在持有 #card("章节 2 梗概") 后都改为跳入章节 3。最短的走法是 #card("选择：周末的计划") 选 #opt("不去")；原博客用的是 #card("选择：对咒语的兴趣") 选 #opt("没什么特别的")，效果相同。

#route-box[#story][
  #card("午休的走廊") #arrow #card("选择：楼梯的传闻")（耗时 100）：默认只有 #opt("不知道") #arrow #card("选择：颇有意思的传闻")：默认只有 #opt("告诉我") #arrow #card("选择：传闻是指")（耗时 100）：默认 #opt("没兴趣") 与 #opt("不知道") 都进 #card("对传闻没兴趣") #arrow #gameover
]
#route-box[#frag][
  #make-cards(
    ("午休的走廊", [递 #card("课间休息")]),
    ("选择：楼梯的传闻", [无需递卡。做成后出现 #opt("告诉我")]),
    ("对传闻没兴趣", [依次递 #card("一如往常的生活")、#card("又是一如往常的生活")]),
    ("选择：传闻是指", [需先持有 #card("选择：楼梯的传闻")；递 #card("探索：放学后的学校", id: 20) #cn(20)。做成后出现 #opt("闹鬼楼梯")]),
  )
]

#route-box[#story][
  #card("选择：传闻是指") 选 #opt("闹鬼楼梯") #arrow #card("闹鬼楼梯") #arrow #card("选择：传闻的事……")：默认只有 #opt("随口打听") 与 #opt("姑且问问")，两项都只是各讲一小段就回到同一个选择，把两项都选一遍。
]
#route-box[#frag][
  #make-cards(
    ("闹鬼楼梯", [需先持有 #card("选择：传闻是指")；无需递卡]),
    ("随口打听", [无需递卡]),
    ("姑且问问看", [需先持有 #card("随口打听")；无需递卡]),
    ("选择：传闻的事……", [依次递 #card("随口打听")、#card("姑且问问看")。做成后出现 #opt("认真打听")]),
    ("认真打听", [递 #card("章节 2 梗概")]),
  )
]

== 探索：放学后的学校

选 #opt("认真打听") 后进入探索。这次的探索有*顺序*，地图上的地点也会随进度增加：

1. *保健室*：向保健室老师打听。接着问下一个找谁：#opt("保健室老师") 与 #opt("片假名老师") 都会回到这个问题，选 #opt("Yukari老师") 才继续。
2. *图书室*（保健室之后才在地图上出现）：找到 Yukari 老师，她提起田径部。回答 #opt("没有这个人") 会绕回来，选 #opt("有这个人") 想起田径部的小菊。
3. *操场*：小菊在部活里，暂时说不上话。
4. *天台*：去天台途中在走廊看见 Yuichi 的身影，探索结束，进入 #card("选择：Yuichi的身影")。

教室可以随时去，只是看看 Yuichi 的书包还在，与进度无关。

#route-box[#story][
  #card("选择：Yuichi的身影")：默认只有 #opt("跟上去") #arrow #card("跟上去") #arrow #card("亲吻")（入手 #card("老师不可信")）#arrow #card("章节 3：Ayano")（耗时 100）#arrow #card("飞奔离去的Ayano") #arrow #card("前往楼梯") #arrow #card("Yuichi的手") #arrow #card("天台", id: 85) #cn(85) #arrow #gameover
]
#route-box[#frag][
  #make-cards(
    ("跟上去", [递 #card("夜晚的走廊")]),
    ("亲吻", [无需递卡]),
    ("章节 3：Ayano", [无需递卡]),
    ("探索：放学后的学校", [卡 74。需先持有 #card("跟上去")；无需递卡], 74),
    ("选择：Yuichi的身影", [需先持有 #card("亲吻")；递 #card("跟上去")。做成后出现 #opt("不管他")]),
    ("飞奔离去的Ayano", [递 #card("回过神来的地方")]),
    ("前往楼梯", [递 #card("Yuichi")]),
    ("Yuichi的手", [递 #card("亲吻")]),
    ("天台", [卡 85。依次递 #card("她的名字")、#card("回荡在走廊的声音")], 85),
  )
]

== 不去图书室

#route-box[#story][
  #card("选择：Yuichi的身影") 选 #opt("不管他") #arrow #card("不管他") #arrow #card("田径部的传闻") #arrow #card("选择：要去的地方")：默认只有 #opt("前往图书室")，又会撞见接吻 #arrow #gameover
]
#route-box[#frag][
  #make-cards(
    ("不管他", [递 #card("Yuichi的背影")]),
    ("田径部的传闻", [依次递 #card("小菊")、#card("想不起约定")]),
    ("选择：要去的地方", [递 #card("老师不可信")。做成后出现 #opt("前往楼梯")]),
  )
]

#route-box[#story][
  #card("选择：要去的地方") 选 #opt("前往楼梯") #arrow #card("章节 3：Ayano") #arrow #card("前往楼梯") #arrow #card("与Yuichi前往楼梯") #arrow #card("选择：与Yuichi……")：默认只有 #opt("但总有一天会分开") #arrow #card("但总有一天会分开") #arrow 再次目击 #card("亲吻") #arrow #gameover
]
#route-box[#frag][
  #make-cards(
    ("与Yuichi前往楼梯", [递 #card("田径部的传闻")]),
    ("但总有一天会分开", [递 #card("亲吻")]),
    ("选择：与Yuichi……", [递 #card("但总有一天会分开")。做成后出现 #opt("想一直在一起")]),
  )
]

== 章节 3A 完成

#route-box[#story][
  #opt("不管他") #arrow #opt("前往楼梯") #arrow #opt("想一直在一起") #arrow #card("想一直在一起") #arrow 未持有 #card("章节 4B 梗概") 时直接 #card("与Yuichi接吻") #arrow #complete（章节 3A）
]
#route-box[#frag][
  #make-cards(
    ("想一直在一起", [无需递卡]),
    ("与Yuichi接吻", [章节终卡 #cn(89)。需先持有 #card("对传闻没兴趣") 与 #card("Yuichi的手")；依次递 #card("午休的走廊")、#card("闹鬼楼梯")、#card("探索：放学后的学校", id: 74) #cn(74)、#card("不管他")、#card("田径部的传闻")、#card("与Yuichi前往楼梯")、#card("想一直在一起")]),
  )
]

做成后进入现实层「章节 3A 读完」：直哉在图书室向由加里老师求证，与千秋去神社祭典，千秋说出姐姐留下的传闻「那所高中的天台有谁都没见过的晚霞」。获得 #card("章节 3A 梗概") #cn(135)。

#tip-box(title: "3B 要等到章节 4 之后")[
  #card("选择：烟花之下，与Yuichi") 需要 #card("章节 4B 梗概") 才会出现，且 #opt("不接吻") 只在本轮讲过章节 4 的 #card("不是我") 时可选。3B 的走法见第 6 章。
]
