local card_177_s5s_20_intro, card_177_s5s_20_resolve, card_177_s5s_20_step3, card_177_s5s_20_step4, card_177_s5s_20_step5, card_177_s5s_20_step6, card_177_s5s_20_step7, card_177_s5s_20_step8, v8, v9, v10, v11, v12, v13, v14, v15, v16, v17, v18, v19, v20, v21, v22, v23, v24, v25, v26, v27, v28, v29
card_177_s5s_20_intro = function()
    local card_177_s5s_20_intro, card_177_s5s_20_resolve, card_177_s5s_20_step3, card_177_s5s_20_step4
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(1534, "NONVOICE", "【彩野】「屋上のサクラさん……」")
    vms(1535, "NONVOICE", "彩野さんは、ぽつりと呟いた。")
    vms(1536, "NONVOICE", "【彩野】「……この場面のあらすじは、こんな感じだね」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『サクラさん』のあらすじを作成しました。") -- tr_line:10
    cStopBGMWrap()
    vms(1537, "NONVOICE", "【直哉】「あ、うん……」")
    vms(1538, "NONVOICE", "【直哉】「それでね、彩野さん、これを見てほしいんだ」")
    vms(1539, "NONVOICE", "僕は、彩野さんに屋上で見つけた『日記』と『いつかきみがみるお話。』を渡した。")
    cLoadPlaySE(cGetFileName("se", "se_101"), false)
    vms(1540, "NONVOICE", "彩野さんは日記に目を通すと、小さく頷いた。")
    comPoseLoad("po2_aya_f_1_b")
    vms(1541, "NONVOICE", "【彩野】「サクラさんの日記と、私の日記……」")
    cPlayBGMWrap(cGetFileName("bgm", "bgm_7_x"))
    vms(1542, "NONVOICE", "【直哉】「え、彩野さんのも？」")
    comPoseLoad("po2_aya_f_1_a")
    vms(1543, "NONVOICE", "【彩野】「うん。そう。私たち、交換日記……してたの」")
    vms(1544, "NONVOICE", "【彩野】「直哉くん、これ、どこに？」")
    vms(1545, "NONVOICE", "【直哉】「えっと、屋上にあったんだ。誰が置いたのかは、わからないんだけど……」")
    comPoseLoad("po2_aya_f_1_c")
    vms(1546, "NONVOICE", "【彩野】「そう……」")
    comPoseLoad("po2_aya_f_2_e")
    vms(1547, "NONVOICE", "【彩野】「私たちが病院に入院した時からの、日記……」")
    vms(1548, "NONVOICE", "【彩野】「……」")
    vms(1549, "NONVOICE", "【彩野】「……私、サクラさんと……」")
    vms(1550, "NONVOICE", "【彩野】「……」")
    comPoseLoad("po2_aya_f_1_a")
    vms(1551, "NONVOICE", "【彩野】「……直哉くん」")
    vms(1552, "NONVOICE", "【彩野】「もしかしたら、物語が――浮かぶかもしれない」")
    vms(1553, "NONVOICE", "【彩野】「この、サクラさんの日記と、物語と――直哉くんのおかげで」")
    vms(1554, "NONVOICE", "【直哉】「え？」")
    comPoseLoad("po2_aya_f_1_c")
    vms(1555, "NONVOICE", "【彩野】「……ね、直哉くん。これまでの『物語』を、もう一度見せてもらっていい？」")
    vms(1556, "NONVOICE", "【直哉】「物語……セクション１から４の物語で、いいんだよ_rね？」")
    vms(1557, "NONVOICE", "【彩野】「うん。ごめんね、面倒なこと頼んじゃって」")
    vms(1558, "NONVOICE", "【直哉】「あ、ううん。全然」")
    comPoseLoad("po2_aya_f_1_a")
    vms(1559, "NONVOICE", "すべての物語と言うことは……セクション３Ｂや、４Ｂも入る……か。")
    vms(1560, "NONVOICE", "【直哉】「えっとね、セクション１のあらすじは――」")
    comPoseDelete()
end
card_177_s5s_20_resolve = function()
    oCard.cardAnswerNonvoiceTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(1561, "NONVOICE", "【彩野】「コックリさん……」")
    vms(1562, "NONVOICE", "【直哉】「セクション２のあらすじは――」")
    comPoseDelete()
end
card_177_s5s_20_step3 = function()
    oCard.cardAnswerNonvoiceTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(1563, "NONVOICE", "【彩野】「オマジナイ……」")
    vms(1564, "NONVOICE", "【直哉】「セクション３Ａのあらすじは――」")
    comPoseDelete()
end
card_177_s5s_20_step4 = function()
    oCard.cardAnswerNonvoiceTrue()
    comPoseLoad("po2_aya_f_1_c")
    vms(1565, "NONVOICE", "【彩野】「階段……ユウイチ……」")
    vms(1566, "NONVOICE", "【直哉】「セクション３Ｂのあらすじは――」")
    comPoseDelete()
end
card_177_s5s_20_step5 = function()
    oCard.cardAnswerNonvoiceTrue()
    comPoseLoad("po2_aya_f_1_b")
    vms(1567, "NONVOICE", "【彩野】「キス、しないんだ……」")
    vms(1568, "NONVOICE", "【直哉】「セクション４Ａのあらすじは――」")
    comPoseDelete()
end
card_177_s5s_20_step6 = function()
    oCard.cardAnswerNonvoiceTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(1569, "NONVOICE", "【彩野】「ユウイチ……」")
    vms(1570, "NONVOICE", "【直哉】「セクション４Ｂのあらすじは――」")
    comPoseDelete()
end
card_177_s5s_20_step7 = function()
    oCard.cardAnswerNonvoiceTrue()
    cStopBGMWrap()
    comPoseLoad("po2_aya_f_1_c")
    vms(1571, "NONVOICE", "【彩野】「サクラさん……」")
    comPoseLoad("po2_aya_f_2_e")
    vms(1572, "NONVOICE", "【彩野】「……」")
    vms(1573, "NONVOICE", "【彩野】「……直哉くん」")
    comPoseLoad("po2_aya_f_1_a")
    vms(1574, "NONVOICE", "【彩野】「それとね、『いつかきみがみるお話。』のあらすじも教えて貰って、いい？」")
    vms(1575, "NONVOICE", "【直哉】「……うん。『いつかきみがみるお話。』の、あらすじは――」")
    comPoseDelete()
end
card_177_s5s_20_step8 = function()
    local card_177_s5s_20_intro, card_177_s5s_20_resolve, card_177_s5s_20_step3, card_177_s5s_20_step4, card_177_s5s_20_step5
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_2_e")
    vms(1576, "NONVOICE", "【彩野】「うん……」")
    comPoseLoad("po2_aya_f_1_a")
    cPlayBGMWrap(cGetFileName("bgm", "bgm_1_x"))
    vms(1577, "NONVOICE", "【彩野】「でね、直哉くん。これを元に『あらすじ』をつくることができると思う」")
    vms(1578, "NONVOICE", "【直哉】「あらすじ？ サクラさんの日記から物語のあらすじをつくる、という事？」")
    vms(1579, "NONVOICE", "【彩野】「ちょっと待って。書くもの、かりていいかな？」")
    vms(1580, "NONVOICE", "【直哉】「あ、うん……はい」")
    vms(1581, "NONVOICE", "僕はペンを彩野さんに渡す。")
    vms(1582, "NONVOICE", "【彩野】「ありがとう！」")
    vms(1583, "NONVOICE", "彩野さんは椅子を引くと、机に向かった。")
    comPoseDelete()
    cLoadPlaySE(cGetFileName("se", "se_51"), false)
    wait(120)
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. 179 .. "_a"), "『サクラの日記：９月１３日』のあらすじを作成しました。") -- tr_line:113
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. 180 .. "_a"), "『サクラの日記：７月（書きかけ）』のあらすじを作成しました。") -- tr_line:115
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. 181 .. "_a"), "『サクラの日記：９月１６日』のあらすじを作成しました。") -- tr_line:117
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. 182 .. "_a"), "『サクラの日記：９月１６日（夜）』のあらすじを作成しました。") -- tr_line:119
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. 183 .. "_a"), "『サクラの日記：９月２０日』のあらすじを作成しました。") -- tr_line:121
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. 184 .. "_a"), "『サクラの日記：９月２２日』のあらすじを作成しました。") -- tr_line:123
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. 185 .. "_a"), "『サクラの日記：９月２３日』のあらすじを作成しました。") -- tr_line:125
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. 186 .. "_a"), "『サクラの日記：９月２９日』のあらすじを作成しました。") -- tr_line:127
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. 187 .. "_a"), "『サクラの日記：断片』のあらすじを作成しました。") -- tr_line:129
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. 188 .. "_a"), "『サクラの日記：１０月３日』のあらすじを作成しました。") -- tr_line:131
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. 189 .. "_a"), "『サクラの日記：１１月１２日』のあらすじを作成しました。") -- tr_line:133
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. 190 .. "_a"), "『サクラの日記：２月１３日』のあらすじを作成しました。") -- tr_line:135
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. 93 .. "_a"), "『アヤノの返信：９月２５日』のあらすじを作成しました。") -- tr_line:137
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. 191 .. "_a"), "『アヤノの返信：１０月３０日』のあらすじを作成しました。") -- tr_line:139
    cStopBGMWrap()
    comPoseLoad("po2_aya_f_1_a")
    comPoseLoad("po2_aya_f_1_b")
    vms(1584, "NONVOICE", "【彩野】「このあらすじを元に、物語を作ってみるね」")
    vms(1585, "NONVOICE", "【直哉】「物語を……今の彩野さんが……？」")
    comPoseLoad("po2_aya_f_1_a")
    vms(1586, "NONVOICE", "彩野さんはコクリと頷く。")
    vms(17043, "NONVOICE", "【彩野】「直哉くんに、サクラさんと私の事、教えてあげられると思う」")
    vms(1587, "NONVOICE", "【彩野】「≪昔、書いた物語を辿る≫じゃなくて、≪今、つくりながら≫になるから……」")
    vms(1588, "NONVOICE", "【彩野】「≪物語の途中で≫直哉くんに質問しちゃうかもしれないけど……」")
    vms(1589, "NONVOICE", "【直哉】「あ、うん。そこはもちろん！ なにかあったら、どんどん聞いてくれれば」")
    vms(1590, "NONVOICE", "……。")
    vms(1591, "NONVOICE", "あ、でも、彩野さんが先にあらすじをつくったと言うことは……。")
    cPlayOneshotMusic(cGetFileName("mus", "mus_13"))
    comEffectYellowIn(60)
    wait(60)
    vms(1592, "NONVOICE", "≪あらすじのスキップはできるけど、スキップしていたら物語が追えなくなる≫事もありそうだ……。")
    cPlayOneshotMusic(cGetFileName("mus", "mus_12"))
    comEffectYellowIn(60)
    wait(60)
    vms(1593, "NONVOICE", "≪この物語……セクション５では、あらすじスキップしないで物語を聞く≫事が必要になると思う。注意しないといけないな……。")
    comPoseLoad("po2_aya_f_1_e")
    vms(1594, "NONVOICE", "【彩野】「ありがとう。……二人で協力して、物語をつくろうね」")
    vms(1595, "NONVOICE", "【直哉】「う、うん……」")
    comPoseLoad("po2_aya_f_1_a")
    vms(1596, "NONVOICE", "【彩野】「じゃあ、始めるね」")
    comPoseLoad("po2_aya_f_1_b")
    vms(1597, "NONVOICE", "【彩野】「セクション５、サクラさんとアヤノの物語を」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. 178 .. "_a"), "『セクション５：サクラ』のあらすじを作成しました。") -- tr_line:169
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. 195 .. "_a"), "『セクション５：アヤノ』のあらすじを作成しました。") -- tr_line:171
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        gameSave.myCard[178].hold = 1
        gameSave.myCard[179].hold = 1
        gameSave.myCard[180].hold = 1
        gameSave.myCard[181].hold = 1
        gameSave.myCard[182].hold = 1
        gameSave.myCard[183].hold = 1
        gameSave.myCard[184].hold = 1
        gameSave.myCard[185].hold = 1
        gameSave.myCard[186].hold = 1
        gameSave.myCard[187].hold = 1
        gameSave.myCard[188].hold = 1
        gameSave.myCard[189].hold = 1
        gameSave.myCard[190].hold = 1
        gameSave.myCard[93].hold = 1
        gameSave.myCard[191].hold = 1
        gameSave.myCard[195].hold = 1
        comAyanoTimeRefresh()
    end
    comPoseDelete()
    cStopBGMWrap()
    wait(1)
    comEffectFadeOut(120)
    cPlayBGMWrap(cGetFileName("bgm", "bgm_1_x"))
    wait(1)
    layerLoad(layerName.pose1, cGetFileName("cutin", "tut_0_a"))
    layerLoad(layerName.scene, "")
    switchScreen(0, "", 60)
    wait(60)
    vms(17044, "NONVOICE", "【セクション５について】セクション５では、これまでのように「彩野がカードを見ながら物語を辿る」のではなく、「彩野がカードを見ながら物語を作成する」セクションです。")
    cLoadPlaySE(cGetFileName("se", "se_101"), false)
    wait(1)
    layerLoad(layerName.pose2, cGetFileName("event", "eve_56_x"))
    switchScreen(0, "", 120)
    layerMoveScale(layerName.pose2, 45, 45, 120)
    layerMovePosition(layerName.pose2, 100, -40, 120)
    wait(120)
    vms(17045, "NONVOICE", "【セクション５について】ストーリーモード中、何度か彩野から質問される場面があります。")
    vms(17046, "NONVOICE", "【セクション５について】彩野の言葉に耳をかたむけ、正解のカードを選んでいくことで物語が進行します。")
    wait(120)
    vms(17047, "NONVOICE", "【スキップ……】先ほど、彩野はサクラと彩野の日記の内容をみて、『物語より先にあらすじカード』を作成しました。")
    vms(17048, "NONVOICE", "【スキップ……】つまり、物語が未完成なまま、先に「あらすじ」という物語の枠を決めてしまったことになります。")
    vms(17049, "NONVOICE", "【スキップ……】このため、セクション５ではあらすじスキップを多用すると「物語で語るべき事」を見落としてしまう……かもしれません。")
    cStopBGMWrap()
    wait(1)
    comEffectFadeOut(120)
end
main = function()
    local v8, v9, v10, v11, v12, v13, v14, v15, v16, v17, v18, v19, v20, v21, v22, v23, v24, v25, v26, v27, v28, v29, v30
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[133].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    if gameSave.myCard[134].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    if gameSave.myCard[135].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    if gameSave.myCard[136].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    if gameSave.myCard[137].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    if gameSave.myCard[138].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    if gameSave.myCard[145].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    if gameSave.myCard[25].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_177_s5s_20_intro()
    v8 = 0
    v9 = 0
    v10 = -1
    while v8 < 1 do
        v11 = oCard.selectCardObj()
        if v11 == 133 then
            break
        end
        if v11 == -1 then
            oCard.cancelCard()
            comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
            run(cGetFileName("script", "snr_fragment_main"))
            quit()
        end
        if v9 == 1 then
            oCard.mesNG2()
            vms(1598, "NONVOICE", "セクション１のあらすじは――")
            comPoseDelete()
        end
        if v9 == 0 then
            oCard.mesNG()
            v9 = v9 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_177_s5s_20_resolve()
    v11 = 0
    v12 = 0
    v13 = -1
    while v11 < 1 do
        v14 = oCard.selectCardObj()
        if v14 == 134 then
            break
        end
        if v14 == -1 then
            oCard.cancelCard()
            comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
            run(cGetFileName("script", "snr_fragment_main"))
            quit()
        end
        if v12 == 1 then
            oCard.mesNG2()
            vms(1599, "NONVOICE", "セクション２のあらすじは――")
            comPoseDelete()
        end
        if v12 == 0 then
            oCard.mesNG()
            v12 = v12 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_177_s5s_20_step3()
    v14 = 0
    v15 = 0
    v16 = -1
    while v14 < 1 do
        v17 = oCard.selectCardObj()
        if v17 == 135 then
            break
        end
        if v17 == -1 then
            oCard.cancelCard()
            comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
            run(cGetFileName("script", "snr_fragment_main"))
            quit()
        end
        if v15 == 1 then
            oCard.mesNG2()
            vms(1600, "NONVOICE", "Ｓｅｃｔｉｏｎ３Ａのあらすじ――")
            comPoseDelete()
        end
        if v15 == 0 then
            oCard.mesNG()
            v15 = v15 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_177_s5s_20_step4()
    v17 = 0
    v18 = 0
    v19 = -1
    while v17 < 1 do
        v20 = oCard.selectCardObj()
        if v20 == 136 then
            break
        end
        if v20 == -1 then
            oCard.cancelCard()
            comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
            run(cGetFileName("script", "snr_fragment_main"))
            quit()
        end
        if v18 == 1 then
            oCard.mesNG2()
            vms(1601, "NONVOICE", "セクション３Ｂのあらすじは――")
            comPoseDelete()
        end
        if v18 == 0 then
            oCard.mesNG()
            v18 = v18 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_177_s5s_20_step5()
    v20 = 0
    v21 = 0
    v22 = -1
    while v20 < 1 do
        v23 = oCard.selectCardObj()
        if v23 == 137 then
            break
        end
        if v23 == -1 then
            oCard.cancelCard()
            comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
            run(cGetFileName("script", "snr_fragment_main"))
            quit()
        end
        if v21 == 1 then
            oCard.mesNG2()
            vms(1602, "NONVOICE", "セクション４Ａのあらすじは――")
            comPoseDelete()
        end
        if v21 == 0 then
            oCard.mesNG()
            v21 = v21 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_177_s5s_20_step6()
    v23 = 0
    v24 = 0
    v25 = -1
    while v23 < 1 do
        v26 = oCard.selectCardObj()
        if v26 == 138 then
            break
        end
        if v26 == -1 then
            oCard.cancelCard()
            comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
            run(cGetFileName("script", "snr_fragment_main"))
            quit()
        end
        if v24 == 1 then
            oCard.mesNG2()
            vms(1603, "NONVOICE", "セクション４Ｂのあらすじは――")
            comPoseDelete()
        end
        if v24 == 0 then
            oCard.mesNG()
            v24 = v24 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_177_s5s_20_step7()
    v26 = 0
    v27 = 0
    v28 = -1
    while v26 < 1 do
        v29 = oCard.selectCardObj()
        if v29 == 145 then
            break
        end
        if v29 == -1 then
            oCard.cancelCard()
            comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
            run(cGetFileName("script", "snr_fragment_main"))
            quit()
        end
        if v27 == 1 then
            oCard.mesNG2()
            vms(1604, "NONVOICE", "『いつかきみがみるお話。』の、あらすじは――")
            comPoseDelete()
        end
        if v27 == 0 then
            oCard.mesNG()
            v27 = v27 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_177_s5s_20_step8()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end