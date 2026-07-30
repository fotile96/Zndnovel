local card_27_s1s_280_intro, card_27_s1s_280_resolve, v2, v3, v4, v5
card_27_s1s_280_intro = function()
    local card_27_s1s_280_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(2171, "NONVOICE", "【彩野】「あの子の事……」")
    vms(2172, "NONVOICE", "【彩野】「彼女……」")
    vms(2173, "NONVOICE", "【彩野】「約束してた、子」")
    vms(2174, "NONVOICE", "【彩野】「あの子の名前って……」")
    comPoseDelete()
end
card_27_s1s_280_resolve = function()
    local card_27_s1s_280_intro, card_27_s1s_280_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(2175, "NONVOICE", "【彩野】「サクラさん……」")
    vms(2176, "NONVOICE", "【直哉】「サクラさんのことは、わかる？」")
    comPoseLoad("po2_aya_f_2_e")
    vms(2177, "NONVOICE", "彩野さんは首を横に振った。")
    vms(2178, "NONVOICE", "【彩野】「ごめんね。よくわからないの」")
    vms(2179, "NONVOICE", "【直哉】「彩野さん……。５年間って、なんだろう」")
    comPoseLoad("po2_aya_f_1_c")
    vms(2180, "NONVOICE", "【彩野】「５年……」")
    vms(2181, "NONVOICE", "【直哉】「そう。サクラさんの言っていた言葉。５年、待っていたって」")
    comPoseLoad("po2_aya_f_1_a")
    vms(2182, "NONVOICE", "……そして、ユウイチを愛していた、とも。")
    comPoseLoad("po2_aya_f_2_e")
    vms(2183, "NONVOICE", "【彩野】「……わからないの……なんなんだろう。このお話。なんでこんなお話なんだろう」")
    vms(2184, "NONVOICE", "……彩野さんが『事故』にあってから、今が５年目になる。")
    vms(2185, "NONVOICE", "確かに、『現在』のカレンダーと、彩野さんの『今』のカレンダーを比較すれば、年月の差分は出せるだろう。")
    vms(2186, "NONVOICE", "……でも、本当にそんな事が可能なのか？")
    vms(2187, "NONVOICE", "【直哉】「彩野さん、今、何年かわかる？」")
    comPoseLoad("po2_aya_f_1_a")
    vms(2188, "NONVOICE", "【彩野】「え？ なんで？」")
    vms(2189, "NONVOICE", "【直哉】「……ちょっと、気になって」")
    comPoseLoad("po2_aya_f_1_c")
    vms(2190, "NONVOICE", "【彩野】「でも、私……記憶が……」")
    vms(2191, "NONVOICE", "彩野さんは目を伏せた。")
    vms(2192, "NONVOICE", "【直哉】「あ、ご、ごめん……ごめんなさい」")
    comPoseLoad("po2_aya_f_1_e")
    vms(2193, "NONVOICE", "【彩野】「ん、いいよ。大丈夫だよ。そんなに謝らなくとも」")
    vms(2194, "NONVOICE", "【直哉】「う、うん」")
    comPoseLoad("po2_aya_f_1_a")
    vms(2195, "NONVOICE", "……。")
    vms(2196, "NONVOICE", "彩野さんはすぐに年月を把握できるわけではなかった。どこかに『現在』の年月をメモしている様子もなかった。")
    vms(2197, "NONVOICE", "でも彼女は、物語を語るときに何も見ずに５年、といった。")
    vms(2198, "NONVOICE", "現実とは、関係のない単なる物語上の、『たまたま５年』なのだろうか。")
    vms(2199, "NONVOICE", "それにしても、この物語は……なにか、ところどころ現実とリンクしている。")
    vms(2200, "NONVOICE", "登場人物の名前が『アヤノ』さんなのだから当然といえば……当然なんだけれど。")
    vms(2201, "NONVOICE", "なんだけど……。")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『彼女の名前』のあらすじを作成しました。") -- tr_line:52
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
    card_27_s1s_280_intro()
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
            vms(2202, "NONVOICE", "【彩野】「あの子の、名前は……」")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_27_s1s_280_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end