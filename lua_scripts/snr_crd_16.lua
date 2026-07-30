local card_16_s1s_140_intro, card_16_s1s_140_resolve, v2, v3, v4, v5
card_16_s1s_140_intro = function()
    local card_16_s1s_140_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(1080, "NONVOICE", "【直哉】「この場面は……まあ、なんというか……普通の放課後のシーンだね」")
    vms(1081, "NONVOICE", "【彩野】「うん。朝の教室の様子って、どんな感じだったっけ？」")
    comPoseDelete()
end
card_16_s1s_140_resolve = function()
    local card_16_s1s_140_intro, card_16_s1s_140_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(1082, "NONVOICE", "【彩野】「……」")
    vms(1083, "NONVOICE", "【彩野】「うん。なるほど、朝の教室と放課後の教室。この感じは、『現実』と変わらない気がする」")
    vms(1084, "NONVOICE", "【彩野】「……あ」")
    vms(1085, "NONVOICE", "【直哉】「ん？ どうかした？」")
    vms(1086, "NONVOICE", "【彩野】「直哉くんは、今は社会人さん？ なのかな？」")
    vms(1087, "NONVOICE", "【直哉】「あ、うん。そうだね」")
    vms(1088, "NONVOICE", "【彩野】「やっぱり、社会人になっても、会社の終わりとかはうれしいものなの？」")
    vms(1089, "NONVOICE", "【直哉】「それは、やっぱり……終わったときの気分……」")
    vms(1090, "NONVOICE", "【直哉】「開放感っていうのかな。そういうのは、学生の頃とあんまりかわらない気がするよ」")
    vms(1091, "NONVOICE", "【彩野】「ふふ、じゃあ時計を気にしたり？」")
    vms(1092, "NONVOICE", "【直哉】「うん。そうそう。あと５分でタイムカード押せるのに、っていう」")
    comPoseLoad("po2_aya_f_1_e")
    vms(1093, "NONVOICE", "【彩野】「ふふ、なんかいいな、そういうの」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『放課後』のあらすじを作成しました。") -- tr_line:28
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[9].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_16_s1s_140_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 9 then
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
            vms(1094, "NONVOICE", "【彩野】「朝のクラスの様子って、どんな感じだったかな」")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_16_s1s_140_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end