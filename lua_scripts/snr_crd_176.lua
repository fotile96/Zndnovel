local card_176_s4s_680_step5, card_176_s4s_680_intro, card_176_s4s_680_resolve, card_176_s4s_680_step3, card_176_s4s_680_step4, card_176_s4s_680_step6, v6, v7, v8, v9, v10
card_176_s4s_680_step5 = function()
    local card_176_s4s_680_step5
    cStopBGMWrap()
    comPoseLoad("po2_aya_f_2_e")
    vms(1483, "NONVOICE", "【彩野】「うーん……」")
    vms(1484, "NONVOICE", "【彩野】「直哉くん……」")
    vms(1485, "NONVOICE", "【彩野】「ごめんなさい、考えが上手くまとまらないの」")
    vms(1486, "NONVOICE", "【直哉】「出したカードが間違っていると言うこと？」")
    vms(1487, "NONVOICE", "【彩野】「ううん、渡してくれたカードはあっていると思うんだけど……」")
    comPoseLoad("po2_aya_f_1_c")
    vms(1488, "NONVOICE", "【彩野】「途中でちょっと、集中ができなくなっちゃって」")
    comPoseLoad("po2_aya_f_1_a")
    vms(1489, "NONVOICE", "そういえば、間違ったカード渡してしまった時があった。")
    vms(1490, "NONVOICE", "ということは、この『まとめ』では続いて正解のカードを選ぶ必要がある――つまり、途中一度でもカードの選択を間違えるとだめみたいだ。")
    vms(1491, "NONVOICE", "なかなか厳しいな。もう一度、カードを選び直してみよう……。")
    comPoseDelete()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end
card_176_s4s_680_intro = function()
    local card_176_s4s_680_step5
    cPlayBGMWrap(cGetFileName("bgm", "bgm_7_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(1492, "NONVOICE", "【直哉】「物語――セクション４の終わり、なんだけど――」")
    comPoseLoad("po2_aya_f_2_a")
    vms(1493, "NONVOICE", "【彩野】「どうかしたの？」")
    vms(1494, "NONVOICE", "【直哉】「ここの終わりの部分、他の物語――セクション１とほぼ同じ展開なんだ」")
    vms(1495, "NONVOICE", "【彩野】「あ、そうなんだ。カードを見せてもらっていい？」")
    vms(1496, "NONVOICE", "【直哉】「うん――。あ、その前に、ここまでの物語を、まとめてもいいかな？」")
    comPoseLoad("po2_aya_f_1_a")
    vms(1497, "NONVOICE", "【彩野】「まとめる……？」")
    vms(1498, "NONVOICE", "【直哉】「うん。物語の終わりだから、ここまでの物語の流れを、まとめてみようと思うんだ」")
    comPoseLoad("po2_aya_f_2_a")
    vms(1499, "NONVOICE", "【彩野】「あ、うんなるほどね」")
    vms(1500, "NONVOICE", "【直哉】「とりあえず、物語の途中までの展開をまとめてあるから、まずはこれを見てもらった方がよいと思う」")
    comPoseLoad("po2_aya_f_1_a")
    vms(1501, "NONVOICE", "【彩野】「ふむふむ……」")
    vms(1502, "NONVOICE", "【直哉】「うん。物語の開始から、アヤノさんのノートを調べるところまで、だね」")
    comPoseDelete()
end
card_176_s4s_680_resolve = function()
    oCard.cardAnswerNonvoiceTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(1503, "NONVOICE", "【彩野】「メモを受け取って、それで屋上に……」")
    vms(1504, "NONVOICE", "【直哉】「この少女は、『サクラさん』だね」")
    comPoseLoad("po2_aya_f_2_e")
    vms(1505, "NONVOICE", "【彩野】「サクラさん……」")
    vms(1506, "NONVOICE", "【直哉】「それで教室に戻ったユウイチは、アヤノさんのノートを調べたんだ。そこに書いてあったのが――」")
    comPoseDelete()
end
card_176_s4s_680_step3 = function()
    oCard.cardAnswerNonvoiceTrue()
    comPoseLoad("po2_aya_f_2_e")
    vms(1507, "NONVOICE", "【彩野】「コックリさん……消しゴム……ユキ……」")
    vms(1508, "NONVOICE", "【直哉】「その後、ユウイチは学校を探索してアヤノさんを探したんだけど……」")
    vms(1509, "NONVOICE", "【直哉】「なかなか、アヤノさんは見つからなかった」")
    vms(1510, "NONVOICE", "【直哉】「暫く探し回って、やっとユウイチは屋上でアヤノさんを発見する事ができた」")
    vms(1511, "NONVOICE", "【直哉】「でも、屋上にいたアヤノさんの様子は明らか普段とは違う……普通でなかった」")
    vms(1512, "NONVOICE", "【直哉】「ユウイチが声を掛けても反応しないし、腕を掴んでも振りほどいてしまう」")
    vms(1513, "NONVOICE", "【彩野】「……」")
    vms(1514, "NONVOICE", "【直哉】「そんな中、アヤノさんは屋上のフェンスをのぼりだした――」")
    vms(1515, "NONVOICE", "【直哉】「ユウイチは、アヤノさんを引き戻し、アヤノさんは、意識を――」")
    comPoseDelete()
end
card_176_s4s_680_step4 = function()
    oCard.cardAnswerNonvoiceTrue()
    cStopBGMWrap()
    comPoseLoad("po2_aya_f_2_e")
    vms(1516, "NONVOICE", "【彩野】「うん……」")
    vms(1517, "NONVOICE", "【直哉】「そして、この物語――セクション４は完結したんだけど……」")
    vms(1518, "NONVOICE", "【彩野】「けど……？」")
    vms(1519, "NONVOICE", "【直哉】「セクション４の最後の部分は、セクション１のこのシーンと同じ展開だったんだ――」")
    comPoseDelete()
end
card_176_s4s_680_step6 = function()
    local card_176_s4s_680_step5, card_176_s4s_680_intro, card_176_s4s_680_resolve, card_176_s4s_680_step3
    oCard.cardAnswerTrue()
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(1520, "NONVOICE", "【彩野】「……ということは、この物語……セクション４は、セクション１のユウイチ視点、という事で考えていいのかな？」")
    vms(1521, "NONVOICE", "【直哉】「うん、基本的にはそうだと思う……でも」")
    vms(1522, "NONVOICE", "【直哉】「全く同じ、ではないかも。セクション１では図書室も出てこなかったし、微妙に違う部分はあるから」")
    comPoseLoad("po2_aya_f_2_e")
    vms(1523, "NONVOICE", "【彩野】「一部の場面では重なっている、という感じ？」")
    vms(1524, "NONVOICE", "【直哉】「重なっている、繋がっている……うん。僕もそんな風に思ってる」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『消えたサクラ』のあらすじを作成しました。") -- tr_line:89
    cStopBGMWrap()
    vms(1525, "NONVOICE", "【彩野】「……セクション１……」")
    vms(1526, "NONVOICE", "【彩野】「……物語の、終わり……」")
    comPoseLoad("po2_aya_f_1_c")
    vms(1527, "NONVOICE", "【彩野】「……」")
    wait(1)
    comEffectFadeOut(120)
    vms(1528, "NONVOICE", "僕たちは学校を出た。")
    comSectionCardEndSection()
    doScriptScene = "s4fa-10"
    run(cGetFileName("script", "snr_s4_10_fa"))
    quit()
end
main = function()
    local v6, v7, v8, v9, v10, v11
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[167].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    if gameSave.myCard[168].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    if gameSave.myCard[172].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    if gameSave.myCard[30].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    v6 = false
    card_176_s4s_680_intro()
    v7 = 0
    v8 = 0
    v9 = -1
    while v7 < 1 do
        v10 = oCard.selectCardObj()
        if v10 == 167 then
            break
        end
        if v10 == -1 then
            oCard.cancelCard()
            comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
            run(cGetFileName("script", "snr_fragment_main"))
            quit()
        end
        if v8 == 1 then
            v6 = true
            oCard.mesNG2()
            vms(1529, "NONVOICE", "『選択：アヤノのノート』に、それまでの行動をまとめてあるから、これを見てもらうのが早いかな……。")
            comPoseDelete()
        end
        if v8 == 0 then
            v6 = true
            oCard.mesNG()
            v8 = v8 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_176_s4s_680_resolve()
    v7 = 0
    v8 = 0
    v9 = -1
    while v7 < 1 do
        v10 = oCard.selectCardObj()
        if v10 == 168 then
            break
        end
        if v10 == -1 then
            oCard.cancelCard()
            comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
            run(cGetFileName("script", "snr_fragment_main"))
            quit()
        end
        if v8 == 1 then
            v6 = true
            oCard.mesNG2()
            vms(1530, "NONVOICE", "教室に戻ったユウイチは、アヤノさんのノートを調べた。")
            vms(1531, "NONVOICE", "ノートには名前が書かれていて……")
            comPoseDelete()
        end
        if v8 == 0 then
            v6 = true
            oCard.mesNG()
            v8 = v8 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_176_s4s_680_step3()
    v7 = 0
    v8 = 0
    v9 = -1
    while v7 < 1 do
        v10 = oCard.selectCardObj()
        if v10 == 172 then
            break
        end
        if v10 == -1 then
            oCard.cancelCard()
            comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
            run(cGetFileName("script", "snr_fragment_main"))
            quit()
        end
        if v8 == 1 then
            v6 = true
            oCard.mesNG2()
            vms(1532, "NONVOICE", "ユウイチが強くアヤノさんの身体を引き戻したことにより、アヤノさんは意識を――")
            comPoseDelete()
        end
        if v8 == 0 then
            v6 = true
            oCard.mesNG()
            v8 = v8 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_176_s4s_680_step4()
    v7 = 0
    v8 = 0
    v9 = -1
    while v7 < 1 do
        v10 = oCard.selectCardObj()
        if v10 == 30 then
            break
        end
        if v10 == -1 then
            oCard.cancelCard()
            comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
            run(cGetFileName("script", "snr_fragment_main"))
            quit()
        end
        if v8 == 1 then
            v6 = true
            oCard.mesNG2()
            vms(1533, "NONVOICE", "この物語……セクション４の最後の部分は、セクション１のこのシーンと同じ展開だった――")
            comPoseDelete()
        end
        if v8 == 0 then
            v6 = true
            oCard.mesNG()
            v8 = v8 + 1
            comPoseDelete()
        end
        wait(30)
    end
    if v6 == true then
        card_176_s4s_680_step5()
    end
    card_176_s4s_680_step6()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end