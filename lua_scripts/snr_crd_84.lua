local card_84_s3s_460_intro, card_84_s3s_460_resolve, v2, v3, v4, v5
card_84_s3s_460_intro = function()
    local card_84_s3s_460_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(3602, "NONVOICE", "【彩野】「ごめんなさい、直哉くん……。ちょっとわからなくなっちゃった」")
    vms(3603, "NONVOICE", "【彩野】「ここはどうしてユウイチの腕を振りほどくんだっけ？」")
    comPoseLoad("po2_aya_f_2_d")
    vms(3604, "NONVOICE", "【彩野】「アヤノはどうしてこんなにユウイチを嫌っているの？」")
    vms(3605, "NONVOICE", "【直哉】「それは……」")
    comPoseLoad("po2_aya_f_1_a")
    vms(3606, "NONVOICE", "【彩野】「アヤノがユウイチを拒絶するのは、なにか理由があるんだよね。それはどうしてだったかな？」")
    vms(3607, "NONVOICE", "アヤノさんが拒否した理由――。それは、図書室のあの場面を目撃したからだ。")
    comPoseDelete()
end
card_84_s3s_460_resolve = function()
    local card_84_s3s_460_intro, card_84_s3s_460_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(3608, "NONVOICE", "【彩野】「あ……」")
    comPoseLoad("po2_aya_f_2_e")
    vms(3609, "NONVOICE", "【直哉】「……」")
    comPoseLoad("po2_aya_f_1_c")
    vms(3610, "NONVOICE", "【彩野】「――そっか」")
    vms(3611, "NONVOICE", "【彩野】「直哉くん。ここのあらすじはこうなると思う」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『ユウイチの腕』のあらすじを作成しました。") -- tr_line:27
    vms(3612, "NONVOICE", "【彩野】「……」")
    comPoseLoad("po2_aya_f_2_e")
    vms(3613, "NONVOICE", "【彩野】「……ごめんね」")
    vms(3614, "NONVOICE", "【直哉】「……」")
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[80].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_84_s3s_460_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 80 then
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
            vms(3615, "NONVOICE", "アヤノさんが拒否した理由――。それは、図書室のあの場面を目撃したから……。")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_84_s3s_460_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end