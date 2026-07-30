local card_36_s2s_140_intro, card_36_s2s_140_resolve, v2, v3, v4, v5
card_36_s2s_140_intro = function()
    local card_36_s2s_140_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(2547, "NONVOICE", "【直哉】「ここから、セクション２の物語が始まる、ということかな」")
    vms(2548, "NONVOICE", "【彩野】「うん。そうだと思う。セクション２……。第二章という感じ」")
    vms(2549, "NONVOICE", "【直哉】「あ、それじゃあ――」")
    vms(2550, "NONVOICE", "セクション２ということは、この物語もやっぱりアヤノさんが学校の中を巡る感じの物語になるのだろうか？")
    vms(2551, "NONVOICE", "一応、念のため確認しておこう。僕は彩野さんに、『物語の主人公』のカードを見せることにした。")
    comPoseDelete()
end
card_36_s2s_140_resolve = function()
    local card_36_s2s_140_intro, card_36_s2s_140_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(2552, "NONVOICE", "【直哉】「この物語の主人公も、やっぱり？」")
    vms(2553, "NONVOICE", "【彩野】「うん。アヤノだと思う。このセクションでは」")
    vms(2554, "NONVOICE", "【直哉】「『このセクションでは』？ それじゃあ、もしかしてアヤノさん以外の人物も主人公になるかもしれない、ということ？」")
    vms(2555, "NONVOICE", "【彩野】「たぶん……だけど。その可能性は高いって思うの」")
    vms(2556, "NONVOICE", "【彩野】「私、『この部分の主人公はアヤノだな』って。そんな風に書いていたような気がする」")
    vms(2557, "NONVOICE", "【直哉】「となると、ユウイチやサクラさんにも可能性があるということかな……。物語の主要な人物から考えると」")
    comPoseLoad("po2_aya_f_2_e")
    vms(2558, "NONVOICE", "【彩野】「そうかも……でも、今は……。他の展開まではちょっと思い浮かばないの。ごめんなさい」")
    vms(2559, "NONVOICE", "【直哉】「あ、ううん。もちろん了解。ゆっくり考えよう。とりあえず、このセクションを最後まで進んでみてから、だね」")
    vms(2560, "NONVOICE", "【直哉】「そしたら、また、セクション１の時みたいに新しい展開が浮かぶかもしれないから」")
    comPoseLoad("po2_aya_f_1_a")
    vms(2561, "NONVOICE", "【彩野】「……うん」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『セクション２：アヤノ』のカードを作成しました。") -- tr_line:30
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[126].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_36_s2s_140_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 126 then
            break
        end
        if v5 == -1 then
            oCard.cancelCard()
            comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
            run(cGetFileName("script", "snr_fragment_main"))
            quit()
        end
        if v3 == 1 then
            oCard.mesNG2()
            vms(2562, "NONVOICE", "彩野さんに、『物語の主人公』のカードを見せてみよう。")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_36_s2s_140_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end