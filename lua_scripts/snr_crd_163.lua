local card_163_s4s_330_intro, card_163_s4s_330_resolve, v2, v3, v4, v5
card_163_s4s_330_intro = function()
    local card_163_s4s_330_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(1129, "NONVOICE", "【直哉】「ユウイチが教室に戻ると、室内が荒れていた、という場面だけど――」")
    comPoseLoad("po2_aya_f_2_a")
    vms(1130, "NONVOICE", "【彩野】「『だけど？』」")
    vms(1131, "NONVOICE", "【直哉】「うん、それで、この場面なんだけど――既にあらすじを作成した場面の後半と、展開が同じような感じなんだ」")
    comPoseLoad("po2_aya_f_1_b")
    vms(1132, "NONVOICE", "【彩野】「そうなんだ。その場面のあらすじ、みせてもらっていい？」")
    comPoseDelete()
end
card_163_s4s_330_resolve = function()
    local card_163_s4s_330_intro, card_163_s4s_330_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(1133, "NONVOICE", "【彩野】「……」")
    comPoseLoad("po2_aya_f_1_b")
    vms(1134, "NONVOICE", "【彩野】「ふむ……確かに同じみたいだね」")
    comPoseLoad("po2_aya_f_2_e")
    vms(1135, "NONVOICE", "【彩野】「ちょっと、ここのシーン……気になるかな」")
    vms(1136, "NONVOICE", "【直哉】「気になる？」")
    comPoseLoad("po2_aya_f_1_a")
    vms(1137, "NONVOICE", "【彩野】「うん、なんか……生々しいっていうのかな。頭の中にパッと、映像が浮かぶの」")
    vms(1138, "NONVOICE", "【彩野】「椅子や机や、鞄が倒れてたりするところ」")
    vms(1139, "NONVOICE", "【直哉】「以前、彩野さんが見たかもしれない、ということ？」")
    comPoseLoad("po2_aya_f_1_c")
    vms(1140, "NONVOICE", "【彩野】「うん……似たような事、現実に見たのかな……」")
    comPoseLoad("po2_aya_f_2_d")
    vms(1141, "NONVOICE", "【彩野】「って、さすがに私たちのクラス、誰かが突然暴れ出すなんて事、なかったよね？」")
    vms(1142, "NONVOICE", "【直哉】「はは……うん。悪戯でもこういうのはなかったと思うよ」")
    comPoseLoad("po2_aya_f_1_a")
    vms(1143, "NONVOICE", "【彩野】「だよね……」")
    comPoseLoad("po2_aya_f_2_e")
    vms(1144, "NONVOICE", "【彩野】「でも……それじゃあ、私、どこで見たんだろう……」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『ひっくり返った机』のあらすじを作成しました。") -- tr_line:38
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[155].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_163_s4s_330_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 155 then
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
            vms(1145, "NONVOICE", "ここの展開は、メモを見たときに『興味はない』と伝えた後と同じかな……。")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_163_s4s_330_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end