local card_34_s2s_90_intro, card_34_s2s_90_resolve, card_34_s2s_90_step3, v3, v4, v5, v6, v7, v8, v9
card_34_s2s_90_intro = function()
    local card_34_s2s_90_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(2466, "NONVOICE", "【彩野】「ユウイチと出かけることを決めたアヤノだけど、結局、場所は決めきれなかったんだね」")
    vms(2467, "NONVOICE", "【彩野】「それで廊下で、サクラさんと話してオマジナイを聞く場面」")
    vms(2468, "NONVOICE", "【直哉】「サクラさん……」")
    vms(2469, "NONVOICE", "【彩野】「直哉くん、どうしたの？」")
    vms(2470, "NONVOICE", "【直哉】「うん。これまで彩野さんから聞いた物語に出てくるサクラさんって、二通りの……なんだろう、性格というか、人格というかに……」")
    vms(2471, "NONVOICE", "【直哉】「分かれているような気がするんだ。一人は、この場面に出てきたサクラさん。優しい感じがするね」")
    vms(2472, "NONVOICE", "【彩野】「うん」")
    vms(2473, "NONVOICE", "【直哉】「印象としては、これはセクション１のコックリさんの場面と似ている感じがする」")
    vms(2474, "NONVOICE", "僕は、『放課後のコックリさん』のカードを彩野さんに見せてみた。")
    comPoseDelete()
end
card_34_s2s_90_resolve = function()
    local card_34_s2s_90_intro
    oCard.cardAnswerTrue()
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(2475, "NONVOICE", "【直哉】「もう一人は、セクション１、意識を失った『アヤノ』さんが屋上で出会ったサクラさん」")
    vms(2476, "NONVOICE", "【直哉】「ここの場面のサクラさんって、もう一方のサクラさんとは、ずいぶん印象が違うなって」")
    vms(2477, "NONVOICE", "僕は、『彼女の名前』のカードを彩野さんに見せることにした。")
    comPoseDelete()
end
card_34_s2s_90_step3 = function()
    local card_34_s2s_90_intro, card_34_s2s_90_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_2_e")
    vms(2478, "NONVOICE", "【彩野】「ふむ……なるほど」")
    comPoseLoad("po2_aya_f_1_a")
    vms(2479, "NONVOICE", "【直哉】「それで、サクラさんと彩野さんは、『現実』にも会った可能性が高いと言うことだよ」")
    vms(2480, "NONVOICE", "【彩野】「え？」")
    vms(2481, "NONVOICE", "【直哉】「えっとね。サクラさんの妹――千秋ちゃんに聞いてみたんだ」")
    vms(2482, "NONVOICE", "【彩野】「千秋ちゃん――」")
    comPoseLoad("po2_aya_f_2_e")
    vms(2483, "NONVOICE", "【彩野】「……じゃあ、失礼かもしれないけど……」")
    vms(2484, "NONVOICE", "【彩野】「私はサクラさんに親しくしていた一方で、恐れを抱いていた、という事になるのかな？」")
    vms(2485, "NONVOICE", "【直哉】「うーん、今の情報だけで判断すれば、そうとも言えるけど……サクラさんについてはほとんど情報をしらないんだ。だからまだ結論を出すのは早いかもしれない」")
    comPoseLoad("po2_aya_f_1_a")
    vms(2486, "NONVOICE", "【彩野】「確かに、そうだね……」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『休み時間』のあらすじを作成しました。") -- tr_line:44
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v3, v4, v5, v6, v7, v8, v9, v10
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[21].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    if gameSave.myCard[27].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_34_s2s_90_intro()
    v3 = 0
    v4 = 0
    v5 = -1
    while v3 < 1 do
        v6 = oCard.selectCardObj()
        if v6 == 21 then
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
            vms(2487, "NONVOICE", "『放課後のコックリさん』のカードを彩野さんに見せてみよう。")
            comPoseDelete()
        end
        if v4 == 0 then
            oCard.mesNG()
            v4 = v4 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_34_s2s_90_resolve()
    v6 = 0
    v7 = 0
    v8 = -1
    while v6 < 1 do
        v9 = oCard.selectCardObj()
        if v9 == 27 then
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
            vms(2488, "NONVOICE", "『彼女の名前』のカードを彩野さんに見せてみよう。")
            comPoseDelete()
        end
        if v7 == 0 then
            oCard.mesNG()
            v7 = v7 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_34_s2s_90_step3()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end