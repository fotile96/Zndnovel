#import "../template.typ": *

= 章节 EX1 与 EX2

#chapter-open(entry: [EX1 从章节 4 进入，EX2 从章节 5 进入], unlock: [分别需要 #card("章节 8 梗概") 与 #card("章节 EX1")])[
  两个 EX 章在通关后才能打开，各自补完一个人物：由加里老师与 Yuichi 的过去，以及多年后千秋独自追查真相。
]

== 章节 EX1：Yukari

#story-box(from: "s3s_50_sel", pick: ("告诉我", "闹鬼楼梯", "认真打听", "大声叫他", "有点在意呢", "不接受", "被勾起了兴趣", "试着相信也无妨", "检查课桌", "翻看笔记本", "拉回来", "回家"))[
  从 #card("选择：颇有意思的传闻") 起按章节 3 的主线讲到 #card("选择：Yuichi的身影") 选 #opt("大声叫他") #arrow #card("选择：天台的传闻") 选 #opt("有点在意呢") #arrow #card("章节 4：Yuichi") #arrow #card("图书室的老师") #arrow 持有 #card("章节 8 梗概") 后此处出现 #card("选择：Yukari老师")：默认只有 #opt("不接受")，选它回到章节 4 的正常流程，随后 #opt("被勾起了兴趣") #arrow #opt("试着相信也无妨") #arrow #opt("检查课桌") #arrow #opt("翻看笔记本") #arrow #opt("拉回来") #arrow #opt("回家") 讲到 #card("消失的Sakura") #arrow #complete。全部持卡，零耗时。
]
#frag-box[
  #make-cards(("选择：Yukari老师", [递 #card("章节 8 梗概")。做成后出现 #opt("接受")]))
]
#story-box(from: "s4s_100_sel", pick: ("接受",))[
  回到 #card("选择：Yukari老师") 选 #opt("接受") #arrow 章节 EX1 是一本道，从 #card("春天") 起连续 25 场（天台上的男学生、学校怪谈、共犯、烟花大会、Ayano 的离家出走、那个夏日的图书室、告白……）一路讲到 #complete。全程零耗时。
]
#frag-box[
  #make-cards(("春天", [章节终卡 #cn(118)。递 #card("选择：Yukari老师")]))
]

现实层「章节 EX1 读完」只有一场：由加里老师。获得 #card("章节 EX1") #cn(143)。

== 章节 EX2：千秋

#story-box(from: "s1s_35_sel", pick: ("约好了", "对答卷表示羡慕", "回学校", "Sakura同学", "去中庭", "不硬撑", "再等等"), noskip: ("s5s_140", "s5s_320", "s5s_680"))[
  时间轴停在章节 4，先回到 #card("选择：放学后的约定") 选 #opt("约好了")，按章节 1 的正常路线（#opt("对答卷表示羡慕")、#opt("回学校")）讲到 #card("选择：声音的主人") 选 #opt("Sakura同学")，再按章节 5 的走法读日记：照样不要跳过，#opt("去中庭")、#opt("不硬撑")，讲到 #card("Sakura的日记：11月12日")。持有 #card("章节 EX1") 后这一场末尾出现「他的身影」选择：#opt("再等等") #arrow #card("谁也没有来") #arrow #card("章节 EX2：女学生")：多年后的千秋逐一走访当年的相关者（老教师、筑紫、护士、生父、酒吧老板、彩野母亲），全部是只有对方半边的独白 #arrow #card("第二物语") #arrow #complete。全程零耗时。
]
#frag-box[
  #make-cards(
    ("谁也没有来", [递 #card("章节 EX1")]),
    ("章节 EX2：女学生", [无需递卡]),
    ("第二物语", [章节终卡 #cn(162)。无需递卡]),
  )
]

现实层「章节 EX2 读完」是雪乃弥留之际写下的另一种夏天：出院、开学典礼、游泳池、天象馆、祭典、文化祭的展位「2ndNovel」，直到天台。获得 #card("第二物语")、#card("章节 EX2") #cn(144) 与关键词卡 #card("Naoya")。至此回想与 CG 可以全部登录。

#tip-box(title: "两张容易漏的关键词卡")[
  #card("冬天的告白会失败")、#card("自我暗示") 与 #card("强迫观念") 在章节 5 读到 #card("Sakura的日记：断片") 时入手（要读，不能跳过）；#card("Sakura同学的谜题") 要在章节 2 把谜题全部答对一次。
]
