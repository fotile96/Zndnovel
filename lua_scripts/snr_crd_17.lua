local card_17_s1s_160_intro, card_17_s1s_160_resolve, v2, v3, v4, v5
card_17_s1s_160_intro = function()
    local card_17_s1s_160_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(1310, "NONVOICE", "【彩野】「ユウイチと、ファストフード……」")
    vms(1311, "NONVOICE", "【彩野】「『アヤノ』は、ユウイチの答案をどんな風に受け止めたのが要因で、ファストフードのお店に行く事になったんだろう？」")
    comPoseDelete()
end
card_17_s1s_160_resolve = function()
    local card_17_s1s_160_intro, card_17_s1s_160_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(1312, "NONVOICE", "【彩野】「そっか、羨ましがると、なんだね」")
    comPoseLoad("po2_aya_f_2_d")
    vms(1313, "NONVOICE", "【彩野】「図に乗らせちゃったのかな」")
    vms(1314, "NONVOICE", "【直哉】「彩野さん、ちょっと聞いていい？」")
    comPoseLoad("po2_aya_f_1_a")
    vms(1315, "NONVOICE", "【彩野】「ん、なに？」")
    vms(1316, "NONVOICE", "【直哉】「物語を聞いてて思ったんだけど――」")
    vms(1317, "NONVOICE", "【直哉】「ユウイチと、なんかそういう……コックリさんとかした経験って、ある？」")
    vms(1318, "NONVOICE", "【彩野】「それはないと思うよ」")
    vms(1319, "NONVOICE", "彩野さんは即答した。")
    vms(1320, "NONVOICE", "【彩野】「アイツは、そういうの全然信じない方だったから」")
    comPoseLoad("po2_aya_f_2_d")
    vms(1321, "NONVOICE", "【彩野】「……うん。そこら辺はこの『物語』と『現実』のユウイチと変わらないかもしれないね」")
    vms(1322, "NONVOICE", "【直哉】「そっか……」")
    comPoseLoad("po2_aya_f_1_a")
    vms(1323, "NONVOICE", "【彩野】「……直哉くんは？」")
    vms(1324, "NONVOICE", "【直哉】「僕？ 僕は……どうだろう」")
    vms(1325, "NONVOICE", "【彩野】「……信じたり、する？」")
    vms(1326, "NONVOICE", "【直哉】「……えっと」")
    vms(1327, "NONVOICE", "【直哉】「テレビとかでホラー特集をやってる時は、そりゃ怖いなって思ったりするし、小さい頃はトイレも怖かったり」")
    comPoseLoad("po2_aya_f_2_d")
    vms(1328, "NONVOICE", "【彩野】「ふふ、あるね、そういうの」")
    vms(1329, "NONVOICE", "【直哉】「でもまあ、信じ切っているかって言われたら微妙で、そうでもない、みたいな……」")
    comPoseLoad("po2_aya_f_2_a")
    vms(1330, "NONVOICE", "【彩野】「……」")
    vms(1331, "NONVOICE", "【直哉】「だからまあ、半々ぐらいかもしれない。信じてはないけど、信じたい、みたいな」")
    comPoseLoad("po2_aya_f_2_d")
    vms(1332, "NONVOICE", "【彩野】「なるほどね。そういうの、私もわかる気がする。うん」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『ユウイチとファストフード』のあらすじを作成しました。") -- tr_line:43
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[13].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_17_s1s_160_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 13 then
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
            vms(1333, "NONVOICE", "【彩野】「答案を、どんな風に受け止めたのかな……」")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_17_s1s_160_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end