local card_100_s6s_60_sel_intro, card_100_s6s_60_sel_resolve, v2, v3, v4, v5
card_100_s6s_60_sel_intro = function()
    local card_100_s6s_60_sel_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(304, "NONVOICE", "【直哉】「ここでは、受け取った手紙をどこで読むのか考えているんだね」")
    vms(305, "NONVOICE", "【直哉】「それで、家で読んだ部分の展開は、あらすじのカードをつくってあるんだ」")
    comPoseLoad("po2_aya_f_2_a")
    vms(306, "NONVOICE", "【彩野】「あ、そうなんだ。見せてもらっていい？」")
    comPoseDelete()
end
card_100_s6s_60_sel_resolve = function()
    local card_100_s6s_60_sel_intro, card_100_s6s_60_sel_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(307, "NONVOICE", "【彩野】「あ……」")
    comPoseLoad("po2_aya_f_1_c")
    vms(308, "NONVOICE", "【彩野】「手紙……」")
    comPoseLoad("po2_aya_f_2_e")
    vms(309, "NONVOICE", "【彩野】「私……そっか。こんな風に、読んでた。……うん」")
    vms(310, "NONVOICE", "【直哉】「家の他に、どこかで読んでいた事はある？」")
    vms(311, "NONVOICE", "【彩野】「あ、えっとね……うん」")
    comPoseLoad("po2_aya_f_1_c")
    vms(312, "NONVOICE", "【彩野】「図書室」")
    comPoseLoad("po2_aya_f_1_b")
    vms(313, "NONVOICE", "【彩野】「ほら、サクラさん、学校のウワサ話とか聞いてくることがあったから。落ち着けたし、調べ物をするのに便利だったの」")
    vms(314, "NONVOICE", "【直哉】「うん」")
    comPoseLoad("po2_aya_f_1_c")
    vms(315, "NONVOICE", "【彩野】「よく、読んでた……」")
    vms(316, "NONVOICE", "【彩野】「直哉くん……ここに展開を追加してもらっていい？」")
    vms(317, "NONVOICE", "【直哉】「図書室で読む、だね」")
    comPoseLoad("po2_aya_f_1_b")
    vms(318, "NONVOICE", "【彩野】「……うん」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『選択：どこで読む』の選択肢（図書室で読む）を作成しました。") -- tr_line:35
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[101].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_100_s6s_60_sel_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 101 then
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
            vms(319, "NONVOICE", "手紙を家で読んだときのあらすじは、『サクラからの手紙』になるかな……。")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_100_s6s_60_sel_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end