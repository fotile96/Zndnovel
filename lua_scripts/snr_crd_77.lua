local card_77_s3s_340_intro, card_77_s3s_340_resolve, card_77_s3s_340_step3, v3, v4, v5, v6, v7, v8, v9
card_77_s3s_340_intro = function()
    local card_77_s3s_340_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(3454, "NONVOICE", "【直哉】「陸上部のウワサを『きくちゃん』に聞く場面――」")
    vms(3455, "NONVOICE", "【直哉】「『きくちゃん』に、話を聞くんだね」")
    comPoseLoad("po2_aya_f_2_a")
    vms(3456, "NONVOICE", "【彩野】「きくちゃん……」")
    vms(3458, "NONVOICE", "【直哉】「うん。前に彩野さんが話してくれた『物語』にも登場したんだ」")
    vms(3457, "NONVOICE", "【直哉】「これで『きくちゃん』が物語に関わってくるのは二回目になるかな」")
    vms(3459, "NONVOICE", "【直哉】「きくちゃんについては個別にカードをつくってるよ。これを見てもらった方が早いと思う」")
    comPoseDelete()
end
card_77_s3s_340_resolve = function()
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(3460, "NONVOICE", "【彩野】「……そっか。あ、それで二回目って事は、初めに登場した部分もあるって事だよね？」")
    vms(3461, "NONVOICE", "【直哉】「うん。カードを作ってあるよ」")
    comPoseLoad("po2_aya_f_2_a")
    vms(3462, "NONVOICE", "【彩野】「そのカードも見せてもらっていい？」")
    vms(3463, "NONVOICE", "きくちゃんが最初に登場したシーン……。")
    vms(3464, "NONVOICE", "セクション１の、放課後の約束について聞いた所だったかな。")
    vms(3465, "NONVOICE", "「してる」「していない」「思い出せない」……一番初めにきくちゃんの描写が出てきたのは、どのシーンだっただろう？")
    comPoseDelete()
end
card_77_s3s_340_step3 = function()
    local card_77_s3s_340_intro, card_77_s3s_340_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(3466, "NONVOICE", "【彩野】「ふむ……なるほど」")
    comPoseLoad("po2_aya_f_2_e")
    vms(3467, "NONVOICE", "【彩野】「きくちゃん……」")
    vms(3468, "NONVOICE", "【直哉】「うちのクラスに、こういうニックネームで呼ばれてた子は……ちょっと思い浮かばない」")
    vms(3469, "NONVOICE", "【彩野】「……」")
    comPoseLoad("po2_aya_f_1_a")
    vms(3470, "NONVOICE", "【彩野】「でも、ここでも、きくちゃんが出てきたって言うことは、やっぱりなにかしら、物語にとって意味があるキャラクタみたいだね」")
    vms(3471, "NONVOICE", "【直哉】「うん……」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『陸上部のウワサ』のあらすじを作成しました。") -- tr_line:40
    vms(3472, "NONVOICE", "きくちゃん、か……")
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v3, v4, v5, v6, v7, v8, v9, v10
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[129].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    if gameSave.myCard[6].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_77_s3s_340_intro()
    v3 = 0
    v4 = 0
    v5 = -1
    while v3 < 1 do
        v6 = oCard.selectCardObj()
        if v6 == 129 then
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
            vms(3473, "NONVOICE", "きくちゃんについてのカードを見せてみよう。")
            comPoseDelete()
        end
        if v4 == 0 then
            oCard.mesNG()
            v4 = v4 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_77_s3s_340_resolve()
    v6 = 0
    v7 = 0
    v8 = -1
    while v6 < 1 do
        v9 = oCard.selectCardObj()
        if v9 == 6 then
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
            vms(3474, "NONVOICE", "セクション１の、放課後の約束について聞いた所だったかな……。")
            comPoseDelete()
        end
        if v7 == 0 then
            oCard.mesNG()
            v7 = v7 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_77_s3s_340_step3()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end