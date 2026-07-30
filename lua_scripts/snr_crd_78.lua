local card_78_s3s_350_sel_intro, card_78_s3s_350_sel_resolve, v2, v3, v4, v5
card_78_s3s_350_sel_intro = function()
    local card_78_s3s_350_sel_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_2_e")
    vms(3475, "NONVOICE", "【彩野】「直哉くん、ここの場面なんだけど……」")
    comPoseLoad("po2_aya_f_1_c")
    vms(3476, "NONVOICE", "【彩野】「嫌な感じ……図書室に行くと、何か、良くないことが起きるような気がするの」")
    vms(3477, "NONVOICE", "彩野さんは眉間に皺を寄せながら言った。")
    vms(3478, "NONVOICE", "【彩野】「なんだろう、先生に関わるような……」")
    comPoseLoad("po2_aya_f_1_a")
    vms(3479, "NONVOICE", "【彩野】「先生に、なにか感情を抱いたと思うの。それが、なんだったのかなって……」")
    vms(3480, "NONVOICE", "アヤノさんが『先生』に抱いた感情。それは――")
    comPoseDelete()
end
card_78_s3s_350_sel_resolve = function()
    local card_78_s3s_350_sel_intro, card_78_s3s_350_sel_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_2_e")
    vms(3481, "NONVOICE", "【彩野】「先生は信用できない……。こういう風にアヤノが思った……」")
    vms(3482, "NONVOICE", "【直哉】「うん。この後に展開する物語を見て、ね」")
    vms(3483, "NONVOICE", "ユカリ先生とユウイチが図書室で抱き合っている場面は――必要があったら見せることにしよう。")
    vms(3484, "NONVOICE", "僕から進んで、彩野さんには――見せたくなかった。")
    comPoseLoad("po2_aya_f_1_a")
    vms(3485, "NONVOICE", "【彩野】「直哉くん、ここは……やっぱり図書室に行くことが、『良くない事』を引き起こしてるような気がする」")
    vms(3486, "NONVOICE", "【直哉】「それじゃあ他の場所に？」")
    vms(3487, "NONVOICE", "【彩野】「うん。ここでは階段のウワサを聞いてるんだから、やっぱりウワサされてる場所に行って、調べてみてもいいと思う」")
    vms(3488, "NONVOICE", "【直哉】「直接、階段に行ってみるって事かな？」")
    vms(3489, "NONVOICE", "【彩野】「うん。カードをつくってもらっていい？」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『選択：向かう場所』の選択肢（階段へ）を作成しました。") -- tr_line:31
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[107].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_78_s3s_350_sel_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 107 then
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
            vms(3490, "NONVOICE", "【彩野】「『先生は――』なんて思ったんだろう」")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_78_s3s_350_sel_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end