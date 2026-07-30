local card_54_s2s_370_intro, card_54_s2s_370_resolve, v2, v3, v4, v5
card_54_s2s_370_intro = function()
    local card_54_s2s_370_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(2901, "NONVOICE", "【彩野】「アヤノが、『まあやってもソンは無いんだし』って、オマジナイに取り掛かる場面」")
    vms(2902, "NONVOICE", "【直哉】「そうだね。どちらかというと、あまり積極的には取り組んでない感じ」")
    vms(2903, "NONVOICE", "【彩野】「うん」")
    vms(2904, "NONVOICE", "【直哉】「となると、この『やってソンはないオマジナイ』はこの場面と同じような感じなのかな」")
    comPoseDelete()
end
card_54_s2s_370_resolve = function()
    local card_54_s2s_370_intro, card_54_s2s_370_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(2905, "NONVOICE", "【彩野】「そっか。オマジナイに対して、『たぶん効く』と『やってソンはない』って思うと、どちらも同じような感じになるんだ」")
    vms(2906, "NONVOICE", "【直哉】「うん。これまでの流れを考えると、あまり物語的にはいい流れとは言えないかも」")
    vms(2907, "NONVOICE", "【彩野】「そうだね……ちょっといやな感じ、するね」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『やってソンはないと思う』のあらすじを作成しました。") -- tr_line:20
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[53].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_54_s2s_370_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 53 then
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
            vms(2908, "NONVOICE", "たぶん効くかなって、オマジナイに対して思った場面があったな……。")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_54_s2s_370_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end