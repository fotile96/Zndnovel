local card_82_s3s_380_intro, card_82_s3s_380_resolve, v2, v3, v4, v5
card_82_s3s_380_intro = function()
    local card_82_s3s_380_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(3561, "NONVOICE", "【彩野】「直哉くん、この場面なんだけど……」")
    comPoseLoad("po2_aya_f_1_c")
    vms(3562, "NONVOICE", "【彩野】「お話をまとめようと思うんだけど、頭の中でうまく整理ができなくて……」")
    vms(3563, "NONVOICE", "彩野さんはそう言うと、視線を落とした。")
    vms(3564, "NONVOICE", "【直哉】「えっとね、この場面は、混乱したアヤノさんが、図書室から教室に行って――」")
    vms(3565, "NONVOICE", "【直哉】「その後、教室から屋上へいった場面……かな」")
    comPoseLoad("po2_aya_f_1_a")
    vms(3566, "NONVOICE", "【彩野】「うん。私もそう思うんだけど……なにか、それだけじゃないような気がして」")
    vms(3567, "NONVOICE", "【直哉】「それだけじゃない？」")
    comPoseLoad("po2_aya_f_2_e")
    vms(3568, "NONVOICE", "【彩野】「どこか……何かが足りないの」")
    vms(3569, "NONVOICE", "【直哉】「えっと、分岐があるという感じ？」")
    comPoseLoad("po2_aya_f_1_a")
    vms(3570, "NONVOICE", "【彩野】「あ、ううん。分岐とは違う感じがする」")
    vms(3571, "NONVOICE", "【彩野】「この場面と似たような『物語』があるような気がして」")
    vms(3572, "NONVOICE", "【直哉】「同じ展開、と言うこと？……」")
    vms(3573, "NONVOICE", "【彩野】「うん……何かが、繋がっているような気がする」")
    vms(3574, "NONVOICE", "【直哉】「繋がり……」")
    vms(3575, "NONVOICE", "もう一度、考えてみよう。")
    vms(3576, "NONVOICE", "アヤノさんは、気がつくと教室にいた。そして、屋上に……。")
    vms(3577, "NONVOICE", "……屋上。")
    vms(3578, "NONVOICE", "他の『物語』で、屋上が出てくる箇所。")
    vms(3579, "NONVOICE", "複数あるけれど、どこの場面……？")
    vms(3580, "NONVOICE", "『混乱したアヤノさん』が屋上に行く場面と言えば……？")
    vms(3581, "NONVOICE", "……。")
    vms(3582, "NONVOICE", "そうだ。")
    vms(3583, "NONVOICE", "確か、サクラさんとコックリさんをした後、気が付いたら――")
    comPoseDelete()
end
card_82_s3s_380_resolve = function()
    local card_82_s3s_380_intro, card_82_s3s_380_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(3584, "NONVOICE", "【彩野】「気がついたら屋上」")
    vms(3585, "NONVOICE", "【直哉】「うん。ここの『白い光』の部分が繋がってるのかなって」")
    comPoseLoad("po2_aya_f_1_a")
    vms(3586, "NONVOICE", "【彩野】「あ……うん。そっか……」")
    vms(3587, "NONVOICE", "【直哉】「直接的な『お話』の繋がりでは――セクション１の前後とは繋がっていないんだけど、部分部分が繋がってる感じがしたんだ」")
    vms(3588, "NONVOICE", "【彩野】「うん、なるほど。確かにそんな感じ、するね」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『走り去るアヤノ』のあらすじを作成しました。") -- tr_line:46
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[24].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_82_s3s_380_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 24 then
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
            vms(3589, "NONVOICE", "セクション１、コックリさんの後――")
            vms(3590, "NONVOICE", "彩野さんは気がついたら屋上にいた。")
            vms(3591, "NONVOICE", "あの場面と、このシーン。")
            vms(3592, "NONVOICE", "……『繋がり』が、ある？")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_82_s3s_380_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end