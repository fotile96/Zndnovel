local card_154_s4s_160_sel_intro, card_154_s4s_160_sel_resolve, v2, v3, v4, v5
card_154_s4s_160_sel_intro = function()
    local card_154_s4s_160_sel_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(982, "NONVOICE", "【直哉】「サクラさんからメモを見せてもらった時の行動だね」")
    vms(983, "NONVOICE", "【直哉】「それで、『廊下のユウイチ』の展開のあらすじもつくってあるんだ」")
    comPoseLoad("po2_aya_f_2_a")
    vms(984, "NONVOICE", "【彩野】「あ、見せてもらっていい？」")
    vms(985, "NONVOICE", "【直哉】「うん……」")
    vms(986, "NONVOICE", "【直哉】「でも、ちょっと注意してね。展開は良くない……バッドエンドなんだ」")
    comPoseDelete()
end
card_154_s4s_160_sel_resolve = function()
    local card_154_s4s_160_sel_intro, card_154_s4s_160_sel_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_c")
    vms(987, "NONVOICE", "【彩野】「あ……」")
    vms(988, "NONVOICE", "【彩野】「……」")
    comPoseLoad("po2_aya_f_2_e")
    vms(989, "NONVOICE", "【彩野】「うん……確かに、これは良くない結末だね」")
    vms(990, "NONVOICE", "【直哉】「でね。ちょっと考えてみたんだけど――」")
    vms(991, "NONVOICE", "【直哉】「これまで彩野さんが話してくれた『物語』って、こんな感じでサクラさんから質問を受けて答える部分が結構たくさんあって――」")
    comPoseLoad("po2_aya_f_1_a")
    vms(992, "NONVOICE", "【彩野】「質問？」")
    vms(993, "NONVOICE", "【直哉】「うん。『コックリさんに興味がある？』とか、『オマジナイは？』、『階段のウワサは？』とか……」")
    comPoseLoad("po2_aya_f_2_d")
    vms(994, "NONVOICE", "【彩野】「……七不思議だ」")
    vms(995, "NONVOICE", "【直哉】「そうそう。でね。質問に対して、『興味を抱いてない』って答えた場合、やっぱりどれも結末はよくなかったんだ」")
    comPoseLoad("po2_aya_f_1_c")
    vms(996, "NONVOICE", "【彩野】「……よくない結末……バッドエンド」")
    vms(997, "NONVOICE", "【直哉】「うん。そういう事」")
    comPoseLoad("po2_aya_f_1_a")
    vms(998, "NONVOICE", "【彩野】「……そっか。それじゃあ、ここも」")
    vms(999, "NONVOICE", "僕は頷いた。")
    vms(1000, "NONVOICE", "【彩野】「直哉くん、『興味を惹かれた』展開、つくってもらっていい？」")
    vms(1001, "NONVOICE", "【直哉】「うん、了解」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『選択：メモを見たとき』の選択肢（興味を惹かれた）を作成しました。") -- tr_line:39
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
    card_154_s4s_160_sel_intro()
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
            vms(1002, "NONVOICE", "『廊下のユウイチ』のあらすじを見せてみよう。")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_154_s4s_160_sel_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end