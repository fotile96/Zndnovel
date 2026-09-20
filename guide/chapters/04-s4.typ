#import "../template.typ": *

= 章节 4A / 4B：Yuichi 的视点

#chapter-open(entry: [章节 3 的 #card("选择：Yuichi的身影") 选 #opt("大声叫他")], unlock: [持有 #card("章节 3A 梗概")])[
  视点切到 Yuichi：口袋里多出一张字条，写着「谁都没见过的晚霞的秘密」。本章两段探索都要求把地图走满，四张选择卡一层套一层。结尾分成 4A（Sakura 消失）与 4B（等 Sakura），后者的现实层剧本是全篇的转折。
]

== 进入章节 4

#story-box(from: "s3s_300_sel", pick: ("大声叫他", "不是我", "前往楼梯", "想一直在一起"))[
  #card("选择：Yuichi的身影") 选 #opt("大声叫他") #arrow #card("口袋里的字条") #arrow #card("选择：天台的传闻")：默认只有 #opt("不是我") #arrow #card("不是我") #arrow 折回章节 3 的 #card("田径部的传闻")。之后全是持卡场景，#card("选择：要去的地方") 选 #opt("前往楼梯")、#card("选择：与Yuichi……") 选 #opt("想一直在一起")，一路跳过到章节 3A #complete（零耗时）。
]
#frag-box[
  #make-cards(
    ("口袋里的字条", [递 #card("选择：Yuichi的身影")]),
    ("不是我", [递 #card("田径部的传闻")]),
    ("选择：天台的传闻", [递 #card("不是我")。做成后出现 #opt("有点在意呢")]),
  )
]

#story-box(from: "s4s_30_sel", pick: ("有点在意呢",))[
  #card("选择：天台的传闻") 选 #opt("有点在意呢") #arrow #card("有点在意呢")：耗时 100，#timeover
]
#frag-box[
  #make-cards(("有点在意呢", [递 #card("章节 3A 梗概")]))
]
#story-box(from: "s4s_51")[
  从 #card("有点在意呢") 接着讲 #arrow #card("章节 4：Yuichi")：又是耗时 100，#timeover
]
#frag-box[
  #make-cards(("章节 4：Yuichi", [需先持有 #card("有点在意呢")；无需递卡]))
]
#story-box(from: "s4s_60", pick: ("没有兴趣",))[
  从 #card("章节 4：Yuichi") 接着讲 #arrow #card("图书室的老师") #arrow #card("好像在哪里见过的少女") #arrow #card("选择：看到字条时")：默认只有 #opt("没有兴趣") #arrow #card("没有兴趣") #timeover
]
#frag-box[
  #make-cards(
    ("图书室的老师", [递 #card("亲吻")]),
    ("好像在哪里见过的少女", [递 #card("Sakura")]),
    ("没有兴趣", [递 #card("中庭的人群")]),
  )
]

== 探索：Ayano 怎么了？

地图七个点：教室、走廊、天台、音乐室、美术室、中庭、操场。*每个点各去两次*，然后第三次去走廊，探索结束。探索途中沙漏不动，结束时计 25。

#story-box(from: "s4s_160_sel", pick: ("没有兴趣",))[
  从 #card("选择：看到字条时") 接着讲，选 #opt("没有兴趣") #arrow #card("没有兴趣")（已持卡，跳过）#arrow #card("探索：Ayano怎么了？") #arrow #card("走廊上的Yuichi") #arrow #gameover。探索只需走这一遍：它的卡要递『走廊上的Yuichi』，而这一轮已经把『走廊上的Yuichi』讲到了。
]
#frag-box[
  #make-cards(
    ("走廊上的Yuichi", [递 #card("约定不守可不行")]),
    ("探索：Ayano怎么了？", [递 #card("走廊上的Yuichi")]),
    ("选择：看到字条时", [递 #card("走廊上的Yuichi")。做成后出现 #opt("被勾起了兴趣")]),
  )
]

== 字条、课桌、笔记本

#story-box(from: "s4s_160_sel", pick: ("被勾起了兴趣", "真无聊"))[
  #card("选择：看到字条时") 选 #opt("被勾起了兴趣") #arrow #card("选择：字条的内容")：默认只有 #opt("真无聊") #arrow #card("觉得真无聊") #arrow #card("翻倒的课桌") #arrow 没有「相信」就只能 #card("天台的人影")：沙漏在这里满 #timeover #deadend
]
#frag-box[
  #make-cards(
    ("觉得真无聊", [无需递卡]),
    ("翻倒的课桌", [递 #card("没有兴趣")]),
    ("天台的人影", [递 #card("走廊上的Yuichi")]),
    ("选择：字条的内容", [递 #card("天台的人影")。做成后出现 #opt("试着相信也无妨")]),
  )
]

#story-box(from: "s4s_290_sel", pick: ("试着相信也无妨", "天台的人影"))[
  #card("选择：字条的内容") 选 #opt("试着相信也无妨") #arrow #card("试着相信也无妨") #arrow #card("翻倒的课桌") #arrow #card("选择：Ayano的课桌")：默认只有 #opt("天台的人影") #arrow #gameover
]
#frag-box[
  #make-cards(
    ("试着相信也无妨", [无需递卡]),
    ("选择：Ayano的课桌", [需先持有 #card("选择：字条的内容")；递 #card("试着相信也无妨")。做成后出现 #opt("检查课桌")]),
  )
]

#story-box(from: "s4s_360_sel", pick: ("检查课桌", "寻找Ayano"))[
  #card("选择：Ayano的课桌") 选 #opt("检查课桌") #arrow #card("查看Ayano的课桌") #arrow #card("选择：Ayano的笔记本")：默认只有 #opt("寻找Ayano") #arrow #card("天台的人影") #arrow #gameover
]
#frag-box[
  #make-cards(
    ("查看Ayano的课桌", [无需递卡]),
    ("选择：Ayano的笔记本", [需先持有 #card("好像在哪里见过的少女")；依次递 #card("有点在意呢")、#card("Sakura")、#card("选择：看到字条时")、#card("试着相信也无妨")、#card("查看Ayano的课桌")。做成后出现 #opt("翻看笔记本")]),
  )
]

== 探索：Ayano 的下落，以及 4A 结局

#story-box(from: "s4s_420_sel", pick: ("翻看笔记本", "抓住手臂"))[
  #card("选择：Ayano的笔记本") 选 #opt("翻看笔记本") #arrow #card("写在笔记本上的名字") #arrow #card("探索：Ayano的下落")：地图八个点（比上次多一个图书室），*每个点各去两次*，然后第三次去天台 #arrow #card("选择：将Ayano――")：默认只有 #opt("抓住手臂") #arrow #card("抓住手臂") #timeover #deadend。这段探索同样只走一遍：它的卡要递『选择：将Ayano――』，后者又要递『抓住手臂』，两张都已在这一轮讲到。
]
#frag-box[
  #make-cards(
    ("写在笔记本上的名字", [依次递 #card("不好的结果")、#card("橡皮上写名字")]),
    ("抓住手臂", [递 #card("Yuichi的背影")]),
    ("选择：将Ayano――", [递 #card("抓住手臂")。做成后出现 #opt("拉回来")]),
    ("探索：Ayano的下落", [递 #card("选择：将Ayano――")]),
  )
]

#story-box(from: "s4s_490_sel", pick: ("拉回来", "回家"))[
  #card("选择：将Ayano――") 选 #opt("拉回来") #arrow #card("Ayano恢复意识") #arrow #card("选择：放学后的学校")：默认只有 #opt("回家") #arrow #card("消失的Sakura") #arrow #complete（章节 4A）
]
#frag-box[
  #make-cards(
    ("Ayano恢复意识", [递 #card("Yuichi救下Ayano")]),
    ("消失的Sakura", [章节终卡 #cn(176)。依次递 #card("选择：Ayano的笔记本")、#card("写在笔记本上的名字")、#card("Ayano恢复意识")、#card("有谁在呼唤")]),
  )
]

做成后进入现实层「章节 4A 读完」：直哉送彩野回家后遇上阵雨，在学校撞见不愿回家的千秋，把她带回自己家过夜。获得 #card("章节 4A 梗概") #cn(137)，文库第 2 本解锁。

== 4B：等 Sakura

#frag-box[
  #make-cards(("选择：放学后的学校", [递 #card("章节 4A 梗概")。做成后出现 #opt("等Sakura")]))
]
#story-box(from: "s4s_670_sel", pick: ("等Sakura",))[
  #card("选择：放学后的学校") 选 #opt("等Sakura") #arrow #card("章节 4：Ayano")：耗时 100，#timeover
]
#frag-box[
  #make-cards(("章节 4：Ayano", [无需递卡]))
]
#story-box(from: "s4s_710")[
  从 #card("章节 4：Ayano") 接着讲 #arrow #card("等Sakura") #arrow #complete（章节 4B）
]
#frag-box[
  #make-cards(("等Sakura", [章节终卡 #cn(175)。需先持有 #card("消失的Sakura")；无需递卡]))
]

现实层「章节 4B 读完」是本作的转折：彩野告诉直哉，故事到此为止、再也讲不下去了；直哉买花陪她上天台，说出 Yuichi 是从这里坠落的。剧本中两处只有单一选项的按钮 #opt("紧紧抱住")、#opt("轻轻吻上去") 直接按下即可。之后是酒吧老板转交 Yuichi 寄存的威士忌，以及深夜彩野打来的电话。获得 #card("章节 4B 梗概") #cn(138)，文库第 5 本解锁。
