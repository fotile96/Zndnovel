local card_158_e2s_20_main, v1, v2
card_158_e2s_20_main = function()
    local card_158_e2s_20_main, v1, v2, v3
    cPlayBGMWrap(cGetFileName("bgm", "bgm_1_x"))
    wait(1)
    layerLoad(layerName.pose1, cGetFileName("bg", "bg_1_b_0"))
    switchScreen(0, "", 60)
    wait(120)
    layerLoad(layerName.pose1, cGetFileName("bg", "bg_1_c_0"))
    switchScreen(0, "", 60)
    wait(120)
    layerLoad(layerName.pose1, cGetFileName("bg", "bg_1_a_0"))
    switchScreen(0, "", 60)
    wait(120)
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『セクションＥＸ２：女子生徒』のあらすじが作成されました。") -- tr_line:16
    gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
    comPoseDelete()
end
main = function()
    local v1
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    card_158_e2s_20_main()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end