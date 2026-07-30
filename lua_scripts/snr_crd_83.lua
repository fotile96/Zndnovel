local card_83_s3s_410_intro, card_83_s3s_410_resolve, v2, v3, v4, v5
card_83_s3s_410_intro = function()
    local card_83_s3s_410_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(3593, "NONVOICE", "【直哉】「アヤノさんが階段にいると、男の人の声が聞こえたんだ」")
    vms(3594, "NONVOICE", "【彩野】「えっと、この声の主って――」")
    comPoseDelete()
end
card_83_s3s_410_resolve = function()
    local card_83_s3s_410_intro, card_83_s3s_410_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(3595, "NONVOICE", "【彩野】「ユウイチの声……」")
    vms(3596, "NONVOICE", "【直哉】「ユウイチとアヤノさんは、階段で再会したんだ」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『階段へ』のあらすじを作成しました。") -- tr_line:17
    comPoseLoad("po2_aya_f_2_e")
    vms(3597, "NONVOICE", "【彩野】「ユウイチの声が階段から聞こえたんだ」")
    vms(3598, "NONVOICE", "【彩野】「ユウイチ……」")
    vms(3599, "NONVOICE", "【直哉】「……」")
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[123].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_83_s3s_410_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 123 then
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
            vms(3600, "NONVOICE", "物語の登場人物として、『アイツ』の名前のカードを作ってある。")
            vms(3601, "NONVOICE", "そのカードを見て貰えばいいかな。")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_83_s3s_410_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end