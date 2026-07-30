local card_87_s3s_580_sel_intro, card_87_s3s_580_sel_resolve, v2, v3, v4, v5
card_87_s3s_580_sel_intro = function()
    local card_87_s3s_580_sel_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(3666, "NONVOICE", "【彩野】「直哉くん、ここの場面なんだけど……」")
    vms(3667, "NONVOICE", "【彩野】「『いつかは別れが』を選んだ後のあらすじってどうなるのかな……？」")
    vms(3668, "NONVOICE", "【直哉】「えっと、それは……」")
    vms(3669, "NONVOICE", "【直哉】「あまり良くない、展開になるね」")
    comPoseLoad("po2_aya_f_2_e")
    vms(3670, "NONVOICE", "【彩野】「良くない展開……」")
    comPoseLoad("po2_aya_f_1_a")
    vms(3671, "NONVOICE", "【彩野】「あらすじのカードとか、ある？」")
    vms(3672, "NONVOICE", "【直哉】「えっとね……」")
    vms(3673, "NONVOICE", "この後のシーンのあらすじを説明すると言うことは、必然的に『図書室』に繋がることになる。")
    vms(3674, "NONVOICE", "正直、『あの場面』を彩野さんに余り見せたくはなかった。")
    vms(3675, "NONVOICE", "……")
    vms(3676, "NONVOICE", "でも、彩野さんが見たいというなら……説明はするべきだ。")
    vms(3677, "NONVOICE", "【直哉】「……。うん。カードを作ってあるよ」")
    comPoseDelete()
end
card_87_s3s_580_sel_resolve = function()
    local card_87_s3s_580_sel_intro, card_87_s3s_580_sel_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_2_e")
    vms(3678, "NONVOICE", "【彩野】「あ――」")
    vms(3679, "NONVOICE", "彩野さんはカードの内容に目を通すと、視線を落とした。")
    vms(3680, "NONVOICE", "【直哉】「それでね。このカードを作ったとき、この後の展開は良くない『予感』がするから、ここで分岐を作った方が良いかもしれないって」")
    comPoseLoad("po2_aya_f_1_a")
    vms(3681, "NONVOICE", "【彩野】「うん。そうだね……」")
    vms(3682, "NONVOICE", "【彩野】「『でも、いつかは別れが』の展開が良くないのなら……」")
    vms(3683, "NONVOICE", "【直哉】「分岐、を？」")
    comPoseLoad("po2_aya_f_1_c")
    vms(3684, "NONVOICE", "【彩野】「うん……『ずっと一緒にいたい』、そう思ったのかもしれない」")
    vms(3685, "NONVOICE", "【彩野】「で、でも、直哉くん、私は――！」")
    vms(3686, "NONVOICE", "【直哉】「――わかった。カードを作るね」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『選択：ユウイチと……』の選択肢（ずっと一緒にいたい）を作成しました。") -- tr_line:38
    comPoseLoad("po2_aya_f_1_a")
    vms(3687, "NONVOICE", "【彩野】「……直哉くん……」")
    vms(3688, "NONVOICE", "【直哉】「……」")
    comPoseLoad("po2_aya_f_1_c")
    vms(3689, "NONVOICE", "【彩野】「ごめんなさい」")
    vms(3690, "NONVOICE", "【直哉】「謝らないで、彩野さん」")
    comPoseLoad("po2_aya_f_2_e")
    vms(3691, "NONVOICE", "【彩野】「……」")
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[92].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_87_s3s_580_sel_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 92 then
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
            vms(3692, "NONVOICE", "『でも、いつかは別れが』のあらすじを彩野さんに説明しよう……。")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_87_s3s_580_sel_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end