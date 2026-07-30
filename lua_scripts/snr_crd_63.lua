local card_63_s2s_124_intro, card_63_s2s_124_resolve, v2, v3, v4, v5
card_63_s2s_124_intro = function()
    local card_63_s2s_124_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(3132, "NONVOICE", "【直哉】「この場面のあと、『また、いつもの生活』に戻っちゃうみたいだね」")
    vms(3133, "NONVOICE", "【彩野】「いつもの生活。えっと、直哉くん、そのカード見せて貰っていい？」")
    comPoseDelete()
end
card_63_s2s_124_resolve = function()
    local card_63_s2s_124_intro, card_63_s2s_124_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(3134, "NONVOICE", "【彩野】「なるほど……」")
    vms(3135, "NONVOICE", "【直哉】「アヤノさんのここの答えは、ちょっと茶化したような感じだったね」")
    comPoseLoad("po2_aya_f_2_d")
    vms(3136, "NONVOICE", "【彩野】「それで、この終わりなんだよね……」")
    vms(3137, "NONVOICE", "【彩野】「うーん、となるとサクラさんの質問を真面目に受け取らないと、『何事も起こらず終了』って感じかな」")
    vms(3138, "NONVOICE", "【直哉】「うん……」")
    vms(3139, "NONVOICE", "真剣に向き合う……か。この結果を踏まえて、新しい選択肢を彩野さんに提案してもいいかもしれない。")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『サクラのため息』のあらすじを作成しました。") -- tr_line:22
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[31].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_63_s2s_124_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 31 then
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
            vms(3140, "NONVOICE", "『また、いつもの生活』のカードを彩野さんに見せてみよう。")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_63_s2s_124_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end