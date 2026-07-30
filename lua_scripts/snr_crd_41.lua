local card_41_s2s_190_sel_intro, card_41_s2s_190_sel_resolve, card_41_s2s_190_sel_step3, v3, v4, v5, v6, v7, v8, v9
card_41_s2s_190_sel_intro = function()
    local card_41_s2s_190_sel_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(2688, "NONVOICE", "【直哉】「彩野さん、ここのナゾトキだけど、間違えた部分と正解の部分、両方のあらすじがあるみたいだね」")
    vms(2689, "NONVOICE", "【彩野】「あ、そうなんだ……」")
    vms(2690, "NONVOICE", "【彩野】「じゃあ、えっと、直哉くん。最初に正解の場面のあらすじを見せてもらっていい？」")
    comPoseDelete()
end
card_41_s2s_190_sel_resolve = function()
    local card_41_s2s_190_sel_intro
    oCard.cardAnswerTrue()
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(2691, "NONVOICE", "【彩野】「なるほど……ありがとう」")
    vms(2692, "NONVOICE", "【彩野】「それじゃあ……ナゾトキに間違えたときの場面、教えてくれるかな……」")
    comPoseDelete()
end
card_41_s2s_190_sel_step3 = function()
    local card_41_s2s_190_sel_intro, card_41_s2s_190_sel_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(2693, "NONVOICE", "【彩野】「ふむふむ……」")
    vms(2694, "NONVOICE", "【彩野】「ここの場面、正解と間違いの両方があるってことは、やっぱり後ろの展開に影響があるみたいだね」")
    vms(2695, "NONVOICE", "【直哉】「そうだね……。意味がなかったら、わざわざ二つに分ける必要はないかもしれない」")
    vms(2696, "NONVOICE", "【直哉】「後で見返したときのために、ナゾトキの正解もカードに書いておくね」")
    vms(2697, "NONVOICE", "【彩野】「あ、そうしてもらえると便利かも。ありがとう、直哉くん」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『選択：ナゾトキ』のあらすじを作成しました。") -- tr_line:30
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v3, v4, v5, v6, v7, v8, v9, v10
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[62].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    if gameSave.myCard[42].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_41_s2s_190_sel_intro()
    v3 = 0
    v4 = 0
    v5 = -1
    while v3 < 1 do
        v6 = oCard.selectCardObj()
        if v6 == 62 then
            break
        end
        if v6 == -1 then
            oCard.cancelCard()
            comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
            run(cGetFileName("script", "snr_fragment_main"))
            quit()
        end
        if v4 == 1 then
            oCard.mesNG2()
            vms(2698, "NONVOICE", "【彩野】「ナゾトキに正解したときのあらすじを見せてもらっていい？」")
            comPoseDelete()
        end
        if v4 == 0 then
            oCard.mesNG()
            v4 = v4 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_41_s2s_190_sel_resolve()
    v6 = 0
    v7 = 0
    v8 = -1
    while v6 < 1 do
        v9 = oCard.selectCardObj()
        if v9 == 42 then
            break
        end
        if v9 == -1 then
            oCard.cancelCard()
            comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
            run(cGetFileName("script", "snr_fragment_main"))
            quit()
        end
        if v7 == 1 then
            oCard.mesNG2()
            vms(2699, "NONVOICE", "【彩野】「ナゾトキを間違えちゃったときのあらすじを見せてもらっていい？」")
            comPoseDelete()
        end
        if v7 == 0 then
            oCard.mesNG()
            v7 = v7 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_41_s2s_190_sel_step3()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end