local card_48_s2s_260_sel_intro, card_48_s2s_260_sel_resolve, v2, v3, v4, v5
card_48_s2s_260_sel_intro = function()
    local card_48_s2s_260_sel_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(2794, "NONVOICE", "【彩野】「直哉くん、ここの部分なんだけど……」")
    vms(2795, "NONVOICE", "【直哉】「うん」")
    vms(2796, "NONVOICE", "【彩野】「アヤノの行動、サクラさんの『ナゾトキ』が関係しているかもしれない」")
    vms(2797, "NONVOICE", "【直哉】「サクラさんのナゾトキ……」")
    vms(2798, "NONVOICE", "【彩野】「うん。ちょっと、サクラさんがナゾトキを出題したときのあらすじ、見せてもらっていい？」")
    comPoseDelete()
end
card_48_s2s_260_sel_resolve = function()
    local card_48_s2s_260_sel_intro, card_48_s2s_260_sel_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(2799, "NONVOICE", "【彩野】「そう。ここのナゾトキの問題」")
    vms(2800, "NONVOICE", "【彩野】「あのナゾトキへの取り組みで、物語は変わっていたよね？」")
    vms(2801, "NONVOICE", "【直哉】「そうだね。ナゾトキでは正解と間違いで『物語』が分岐してた」")
    vms(2802, "NONVOICE", "【彩野】「その『結果』が現れるのが、ここのアヤノの選択肢になると思う」")
    vms(2803, "NONVOICE", "【直哉】「選択の、結果……」")
    vms(2804, "NONVOICE", "【彩野】「うん。物語の流れって言うのかな。『あの時この選択をしたから、この結果になる』の」")
    vms(2805, "NONVOICE", "【直哉】「ふむ……。それでナゾトキの影響がここに現れる、という事だね」")
    vms(2806, "NONVOICE", "【彩野】「そういう事だと思う」")
    vms(2807, "NONVOICE", "【直哉】「了解。じゃあ、カードにそのことを書いておくね」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『選択：放課後のオマジナイ』の選択肢について解説を加えました。") -- tr_line:27
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[41].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_48_s2s_260_sel_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 41 then
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
            vms(2808, "NONVOICE", "サクラさんの問題……と言うことは、『ナゾトキ』の場面かな。")
            vms(2809, "NONVOICE", "この部分のあらすじを、彩野さんに見せてみよう。")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_48_s2s_260_sel_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end