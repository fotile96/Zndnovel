local card_43_s2s_210_intro, card_43_s2s_210_resolve, v2, v3, v4, v5
card_43_s2s_210_intro = function()
    local card_43_s2s_210_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(2707, "NONVOICE", "【直哉】「ユウイチの誘いに対してアヤノさんが思い出す場面、だね」")
    vms(2708, "NONVOICE", "【彩野】「直哉くん、えっと、ユウイチが誘ってきた所のあらすじ、もう一度見せてもらっていい？」")
    vms(2709, "NONVOICE", "【直哉】「『夏の予定』だね」")
    comPoseDelete()
end
card_43_s2s_210_resolve = function()
    local card_43_s2s_210_intro, card_43_s2s_210_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(2710, "NONVOICE", "【彩野】「そっか。その場面ではまだ予定を決め切れていなかったから、もう一度聞いてきたんだ」")
    vms(2711, "NONVOICE", "【直哉】「あらすじはこんな感じで問題ないかな？」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『出かける場所』のあらすじを作成しました。") -- tr_line:18
    vms(2712, "NONVOICE", "【彩野】「うん、大丈夫。ありがとう、直哉くん」")
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[32].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_43_s2s_210_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 32 then
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
            vms(2713, "NONVOICE", "『夏の予定』のカードを彩野さんに見せてみよう。")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_43_s2s_210_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end