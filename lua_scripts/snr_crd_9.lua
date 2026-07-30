local card_9_s1s_70_intro, card_9_s1s_70_resolve, v2, v3, v4, v5
card_9_s1s_70_intro = function()
    local card_9_s1s_70_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(3773, "NONVOICE", "【直哉】「この場面は遅れてきたユウイチがアヤノさんをからかう場面だね」")
    vms(3774, "NONVOICE", "【彩野】「うん。そのおかげでアヤノはテスト勉強もできずに時間が来ちゃった感じ」")
    vms(3775, "NONVOICE", "【彩野】「時間。そういえば、教室のこれは今も変わってないね。黒板の上の……」")
    comPoseDelete()
end
card_9_s1s_70_resolve = function()
    local card_9_s1s_70_intro, card_9_s1s_70_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(3776, "NONVOICE", "【彩野】「黒板の上の時計」")
    vms(3777, "NONVOICE", "【直哉】「そうなんだ」")
    vms(3778, "NONVOICE", "【彩野】「うん。同じ物を使ってるよ」")
    vms(3779, "NONVOICE", "さすがに５年も昔になると、教室にどんな物が飾られていたのかの記憶も曖昧になっていた。そこは彩野さんの、強みだ。")
    vms(3780, "NONVOICE", "【直哉】「じゃあ、あらすじを作成してみるね」")
    vms(3781, "NONVOICE", "【彩野】「ちょっとまって。一つ、思うんだ」")
    vms(3782, "NONVOICE", "【直哉】「何だろう？」")
    vms(3783, "NONVOICE", "【彩野】「ユウイチの性格、ちょっと違う感じがする」")
    vms(3784, "NONVOICE", "【直哉】「この物語では？」")
    vms(3785, "NONVOICE", "【彩野】「うん。かなり社交的な感じがする」")
    vms(3786, "NONVOICE", "【直哉】「確かに、ね。こういっちゃあアレだけど、アイツはここまでオープンでもなかったし」")
    vms(3787, "NONVOICE", "【彩野】「なんだろう……理想、に近いのかな？」")
    vms(3788, "NONVOICE", "【直哉】「そこは……わからない。でもとにかく、この物語の『続き』に進んでみよう。そうすれば、なにかわかるかもしれない」")
    vms(3789, "NONVOICE", "【彩野】「『続きの物語』だね。……うん。そうだね」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『朝の教室』のあらすじを作成しました。") -- tr_line:30
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[128].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_9_s1s_70_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 128 then
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
            vms(3790, "NONVOICE", "【彩野】「……みんなが退屈そうに授業中に見るもの、かな……」")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_9_s1s_70_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end