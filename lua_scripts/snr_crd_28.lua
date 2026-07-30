local card_28_s1s_300_intro, card_28_s1s_300_resolve, v2, v3, v4, v5
card_28_s1s_300_intro = function()
    local card_28_s1s_300_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(2203, "NONVOICE", "【彩野】「屋上で、私を……」")
    vms(2204, "NONVOICE", "【彩野】「あの子の名前……」")
    comPoseDelete()
end
card_28_s1s_300_resolve = function()
    local card_28_s1s_300_intro, card_28_s1s_300_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(2205, "NONVOICE", "【彩野】「サクラさん……」")
    comPoseLoad("po2_aya_f_2_d")
    vms(2206, "NONVOICE", "【彩野】「なんか、物語の中とは言え、自分が事故に遭っちゃうのって、やな感じだね、やっぱり」")
    vms(2207, "NONVOICE", "【直哉】「……うん」")
    comPoseLoad("po2_aya_f_2_c")
    vms(2208, "NONVOICE", "【彩野】「そういえば……って言うのも失礼なんだけど、直哉くん」")
    vms(2209, "NONVOICE", "【直哉】「なんだろう？」")
    comPoseLoad("po2_aya_f_1_a")
    vms(2210, "NONVOICE", "【彩野】「この物語、直哉くんは出てこないのかな？」")
    vms(2211, "NONVOICE", "【直哉】「はは……通行人でいいよ。僕は」")
    comPoseLoad("po2_aya_f_1_e")
    vms(2212, "NONVOICE", "【彩野】「もしかしたら後ろの方で出てくるのかも。なんか、ヒーローっぽい役で」")
    vms(2213, "NONVOICE", "【彩野】「屋上から落ちそうになってる私を救ってくれる役とか」")
    comPoseLoad("po2_aya_f_1_a")
    vms(2214, "NONVOICE", "【直哉】「いいね。ついでに空も飛べて宇宙にまで飛ぶんだ」")
    vms(2215, "NONVOICE", "……。")
    vms(2216, "NONVOICE", "でも、その役は……アイツだろうな、やっぱり。")
    vms(2217, "NONVOICE", "【直哉】「それはそれとして。この物語の展開……」")
    vms(2218, "NONVOICE", "【彩野】「うん。非現実ではあるんだけど。ちょっと気になるよね」")
    comPoseLoad("po2_aya_f_2_d")
    vms(2219, "NONVOICE", "【彩野】「まさか、私本当にあの子に落とされちゃった、とか？」")
    vms(2220, "NONVOICE", "【直哉】「いやさすがにそれは……無いと思うよ、うん」")
    comPoseLoad("po2_aya_f_1_a")
    vms(2221, "NONVOICE", "彩野さんが『事故』にあったとき、誰か屋上にいたという話は聞いたことがない。フェンスを消せるわけもない。")
    vms(2222, "NONVOICE", "でも……サクラさん……か。")
    vms(2223, "NONVOICE", "ちょっと由加里先生に調べてみてもらおうか。『現実』にそれっぽい子がいればよいのだけれど。")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『約束はまもらないと』のあらすじを作成しました。") -- tr_line:41
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
    card_28_s1s_300_intro()
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
            vms(2224, "NONVOICE", "【彩野】「あの子の事、気になる……すごく……」")
            vms(2225, "NONVOICE", "【彩野】「あの子の名前……」")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_28_s1s_300_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end