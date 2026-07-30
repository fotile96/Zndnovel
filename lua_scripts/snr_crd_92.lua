local card_92_s3s_590_intro, card_92_s3s_590_resolve, v2, v3, v4, v5
card_92_s3s_590_intro = function()
    local card_92_s3s_590_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(3852, "NONVOICE", "【直哉】「階段でバランスを崩したアヤノさんが、ユウイチに助けられて――慌てて身体を離す所、だね」")
    vms(3853, "NONVOICE", "【直哉】「でも、『いつかは別れが』の後にこのシーンに繋がるのは、どういうことなんだろう」")
    vms(3854, "NONVOICE", "【彩野】「うーん……。直哉くん、この後に展開される場面って、わかる？」")
    vms(3855, "NONVOICE", "この後の展開は、図書室で先生とユウイチが居るところをアヤノさんが目撃する場面だ。")
    vms(3856, "NONVOICE", "……。")
    comPoseDelete()
end
card_92_s3s_590_resolve = function()
    local card_92_s3s_590_intro, card_92_s3s_590_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(3857, "NONVOICE", "【彩野】「あ……」")
    comPoseLoad("po2_aya_f_2_e")
    vms(3858, "NONVOICE", "【彩野】「図書室と……先生……」")
    vms(3859, "NONVOICE", "【直哉】「物語の流れとしては、『いつかは別れが』って、思った後、図書室でユウイチとユカリ先生を目撃する……」")
    vms(3860, "NONVOICE", "【直哉】「そして、その先は――バッドエンド。良くない結末、だね」")
    vms(3861, "NONVOICE", "【直哉】「……」")
    vms(3862, "NONVOICE", "【彩野】「……良くない、結末……」")
    vms(3863, "NONVOICE", "【直哉】「……ここも、分岐を作った方がいいのかな？」")
    vms(3864, "NONVOICE", "【彩野】「あ……うん……そう……かも」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『でも、いつかは別れが』のあらすじを作成しました。") -- tr_line:27
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
    card_92_s3s_590_intro()
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
            vms(3865, "NONVOICE", "この場面のあと、アヤノさんが目撃した、図書室の場面は――")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_92_s3s_590_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end