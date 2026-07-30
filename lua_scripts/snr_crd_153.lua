local card_153_s4s_130_intro, card_153_s4s_130_resolve, v2, v3, v4, v5
card_153_s4s_130_intro = function()
    local card_153_s4s_130_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(970, "NONVOICE", "【直哉】「ここは――図書室で先生と別れて、屋上で『少女』と出会う場面、だね」")
    vms(971, "NONVOICE", "【彩野】「直哉くん、この女の子――」")
    comPoseLoad("po2_aya_f_2_e")
    vms(972, "NONVOICE", "【彩野】「どこかで、見た事があるような気がする……」")
    vms(973, "NONVOICE", "この場面では、直接名前は出ていないけど、これまでの物語の流れを見れば、この子の名前はわかる。")
    vms(974, "NONVOICE", "彩野さんに『この少女の名前』のカードを渡そう。")
    comPoseDelete()
end
card_153_s4s_130_resolve = function()
    local card_153_s4s_130_intro, card_153_s4s_130_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(975, "NONVOICE", "【彩野】「サクラ、さん……」")
    comPoseLoad("po2_aya_f_2_e")
    vms(976, "NONVOICE", "【彩野】「サクラ……」")
    vms(977, "NONVOICE", "【直哉】「うん。サクラさんは、彩野さんがこれまで話してくれた『物語』の中で――」")
    vms(978, "NONVOICE", "【直哉】「何度も出てきている。重要な人物に位置づけられてると思う」")
    vms(979, "NONVOICE", "【彩野】「そうなんだ……」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『どこかで見たことのある少女』のあらすじを作成しました。") -- tr_line:25
    vms(980, "NONVOICE", "【彩野】「サクラさん……」")
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[124].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_153_s4s_130_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 124 then
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
            vms(981, "NONVOICE", "彩野さんに、この『屋上の少女』の名前を教えよう。")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_153_s4s_130_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end