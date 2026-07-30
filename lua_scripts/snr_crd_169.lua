local card_169_s4s_450_sel_intro, card_169_s4s_450_sel_resolve, v2, v3, v4, v5
card_169_s4s_450_sel_intro = function()
    local card_169_s4s_450_sel_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(1302, "NONVOICE", "【直哉】「ここはアヤノさんを捜しに、ユウイチが校内を探索する場面――」")
    vms(1303, "NONVOICE", "【直哉】「それでね。この後の、屋上でアヤノさんを見つける場面のあらすじもつくってあるんだ」")
    comPoseLoad("po2_aya_f_1_b")
    vms(1304, "NONVOICE", "【彩野】「あ、そうなんだ。……それ、教えてもらっていい？」")
    vms(1305, "NONVOICE", "【直哉】「うん。『選択』の場面だね……」")
    comPoseDelete()
end
card_169_s4s_450_sel_resolve = function()
    local card_169_s4s_450_sel_intro, card_169_s4s_450_sel_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(1306, "NONVOICE", "【彩野】「ふむ……」")
    comPoseLoad("po2_aya_f_1_b")
    vms(1307, "NONVOICE", "【彩野】「そっか、ここの場面は『学校内を探索して、屋上でアヤノを見つけた』でひとまとめにしていいみたいだね」")
    vms(1308, "NONVOICE", "【直哉】「了解。カードをつくるね」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『探索：アヤノの居場所』のあらすじを作成しました。") -- tr_line:22
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[170].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_169_s4s_450_sel_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 170 then
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
            vms(1309, "NONVOICE", "屋上の選択――『選択：アヤノを――』のあらすじを見せてみよう。")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_169_s4s_450_sel_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end