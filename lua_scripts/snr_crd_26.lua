local card_26_e2s_10_intro, card_26_e2s_10_resolve, v2, v3, v4, v5
card_26_e2s_10_intro = function()
    local card_26_e2s_10_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    vms(2169, "NONVOICE", "○セクションＥＸ１のあらすじを選択してください。")
end
card_26_e2s_10_resolve = function()
    local card_26_e2s_10_intro, card_26_e2s_10_resolve
    wait(60)
    keyPlaySE(seName.getCard)
    comEffectYellowIn(60)
    wait(120)
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『誰も来ない』のあらすじを作成しました。") -- tr_line:14
    gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[143].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_26_e2s_10_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 143 then
            break
        end
        if v5 == -1 then
            oCard.cancelCard()
            comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
            run(cGetFileName("script", "snr_fragment_main"))
            quit()
        end
        vms(2170, "NONVOICE", "○セクションＥＸ１のあらすじを選択してください。")
        wait(30)
    end
    card_26_e2s_10_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end