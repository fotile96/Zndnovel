local card_11_s1s_90_intro, card_11_s1s_90_resolve, v2, v3, v4, v5
card_11_s1s_90_intro = function()
    local card_11_s1s_90_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(537, "NONVOICE", "【彩野】「お昼休みに話していたこと、コックリさん……」")
    vms(538, "NONVOICE", "【直哉】「彩野さんは、やったことがあるの？」")
    vms(539, "NONVOICE", "【彩野】「それが、よくわからないの」")
    vms(540, "NONVOICE", "【彩野】「でもこんな風にお話を書いたって事は、昔やったことがあったのかもしれないけど……」")
    vms(541, "NONVOICE", "【直哉】「はっきりしない、感じ」")
    vms(542, "NONVOICE", "【彩野】「そう、なの。ごめんなさい」")
    vms(543, "NONVOICE", "【直哉】「いや、そんな。あやまることなんて」")
    vms(544, "NONVOICE", "【彩野】「でも、確か――『約束』だったかな？」")
    vms(545, "NONVOICE", "【直哉】「約束？」")
    vms(546, "NONVOICE", "【彩野】「そう、放課後に……、えっと、誰かとしていた約束」")
    vms(547, "NONVOICE", "【直哉】「うん。そうだね。そういう部分が最初にあった」")
    vms(548, "NONVOICE", "【彩野】「あの『約束』についてって、最初に感じていたこと――」")
    comPoseDelete()
end
card_11_s1s_90_resolve = function()
    local card_11_s1s_90_intro, card_11_s1s_90_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(549, "NONVOICE", "【彩野】「そう……。『思い出せない』」")
    vms(550, "NONVOICE", "【彩野】「その感覚と、似ているのかも。コックリさんをしていたのかどうか、わからない感覚って」")
    vms(551, "NONVOICE", "【直哉】「なんだろう。思い出せそうで思い出せない、そんな感じなのかな」")
    vms(552, "NONVOICE", "彩野さんはコクリと頷いた。")
    vms(553, "NONVOICE", "【彩野】「そう。言葉にすると、そんな感じ」")
    comPoseLoad("po2_aya_f_2_e")
    vms(554, "NONVOICE", "【彩野】「それで、このシーンでアヤノは、ユウイチをコックリさんに誘っているんだよね……うーん……」")
    vms(555, "NONVOICE", "【直哉】「まあ、このことはとりあえず、おいておこう」")
    comPoseLoad("po2_aya_f_1_c")
    vms(556, "NONVOICE", "【彩野】「うん……コックリさんか……なんなんだろう」")
    vms(557, "NONVOICE", "彩野さんはそういうと、小さくため息をついた。")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『昼休みの教室』のあらすじを作成しました。") -- tr_line:36
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[6].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_11_s1s_90_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 6 then
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
            vms(558, "NONVOICE", "【彩野】「一番初め『約束』についてはどう感じていたっけ？」")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_11_s1s_90_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end