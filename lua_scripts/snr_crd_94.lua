local card_94_s8s_50_intro, card_94_s8s_50_resolve, v2, v3, v4, v5
card_94_s8s_50_intro = function()
    vms(3868, "NONVOICE", "○セクション７のあらすじを選択してください。")
end
card_94_s8s_50_resolve = function()
    local card_94_s8s_50_intro, card_94_s8s_50_resolve, v2, v3
    wait(60)
    keyPlaySE(seName.getCard)
    comEffectYellowIn(60)
    wait(200)
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『誰も見たことのない夕焼け』のあらすじを作成しました。") -- tr_line:12
    comSectionCardEndSection()
    doScriptScene = "s8f-10"
    run(cGetFileName("script", "snr_s8_10_f"))
    quit()
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[141].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_94_s8s_50_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 141 then
            break
        end
        if v5 == -1 then
            oCard.cancelCard()
            comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
            run(cGetFileName("script", "snr_fragment_main"))
            quit()
        end
        vms(3869, "NONVOICE", "○セクション７のあらすじを選択してください。")
        wait(30)
    end
    card_94_s8s_50_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end