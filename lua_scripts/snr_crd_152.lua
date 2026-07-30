local card_152_s4s_100_sel_intro, card_152_s4s_100_sel_resolve, v2, v3, v4, v5
card_152_s4s_100_sel_intro = function()
    local card_152_s4s_100_sel_intro, card_152_s4s_100_sel_resolve
    cPlayBGMWrap(cGetFileName("bgm", "bgm_19_x"))
    cLoadPlaySE(cGetFileName("se", "se_106"), false)
    wait(1)
    layerLoad(layerName.pose1, cGetFileName("event", "eve_49_x"))
    switchScreen(0, "", 60)
    wait(60)
    vms(966, "NONVOICE", "セクション８のあらすじカードを選択してください。")
end
card_152_s4s_100_sel_resolve = function()
    local card_152_s4s_100_sel_intro, card_152_s4s_100_sel_resolve
    keyPlaySE(seName.getCard)
    comEffectYellowIn(60)
    wait(200)
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『選択：ユカリ先生』の選択肢（受け入れる）を作成しました。") -- tr_line:18
    gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
    comPoseDelete()
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[142].hold == -1 then
        vms(967, "NONVOICE", "【＊＊＊】この場面を作成するためのカードが足りません。")
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_152_s4s_100_sel_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 142 then
            break
        end
        if v5 == -1 then
            oCard.cancelCard()
            comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
            run(cGetFileName("script", "snr_fragment_main"))
            quit()
        end
        if v3 == 1 then
            vms(968, "NONVOICE", "セクション８のあらすじカードを選択してください。")
        end
        if v3 == 0 then
            vms(969, "NONVOICE", "セクション８のあらすじカードを選択してください。")
        end
        wait(30)
    end
    card_152_s4s_100_sel_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end