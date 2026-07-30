local card_165_s4s_370_intro, card_165_s4s_370_resolve, v2, v3, v4, v5
card_165_s4s_370_intro = function()
    local card_165_s4s_370_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(1166, "NONVOICE", "【直哉】「アヤノさんを探してまわったけど……」")
    vms(1167, "NONVOICE", "【直哉】「結局残念な結果になった所、だね」")
    comPoseLoad("po2_aya_f_2_e")
    vms(1168, "NONVOICE", "【彩野】「バッドエンド……」")
    vms(1169, "NONVOICE", "【直哉】「うん。それでね、この場面については、他のもうひとつの場面と全く同じ展開をしてるんだ」")
    vms(1170, "NONVOICE", "【彩野】「同じ展開？ ……その場面、教えてもらっていい？」")
    comPoseDelete()
end
card_165_s4s_370_resolve = function()
    local card_165_s4s_370_intro, card_165_s4s_370_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(1171, "NONVOICE", "【彩野】「廊下のユウイチ……」")
    comPoseLoad("po2_aya_f_2_e")
    vms(1172, "NONVOICE", "【彩野】「……」")
    vms(1173, "NONVOICE", "【彩野】「バッドエンド……という事は、やっぱりこのシーンに辿り着くまでの展開――」")
    comPoseLoad("po2_aya_f_1_c")
    vms(1174, "NONVOICE", "【彩野】「道筋が良くなかった、という事になるのかな……」")
    vms(1175, "NONVOICE", "【直哉】「うん。そういう事だと思う」")
    comPoseLoad("po2_aya_f_1_a")
    vms(1176, "NONVOICE", "【彩野】「ちょっと、違う展開を考えてみた方がいいみたいだね……」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『屋上の人影』のあらすじを作成しました。") -- tr_line:28
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[157].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_165_s4s_370_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 157 then
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
            vms(1177, "NONVOICE", "この場面と、『廊下のユウイチ』は――同じ展開、かな……。")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_165_s4s_370_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end