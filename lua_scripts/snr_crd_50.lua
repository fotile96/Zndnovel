local card_50_s2s_300_intro, card_50_s2s_300_resolve, v2, v3, v4, v5
card_50_s2s_300_intro = function()
    local card_50_s2s_300_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(2860, "NONVOICE", "【直哉】「消しゴムに名前を書くオマジナイ……。よくある事ではあるんだけど」")
    vms(2861, "NONVOICE", "【彩野】「ん、なにか気になるの？」")
    vms(2862, "NONVOICE", "【直哉】「うん。確か、セクション１でも出てきたんだ。消しゴム」")
    vms(2863, "NONVOICE", "【直哉】「えっとね、放課後の約束について考えるところで――」")
    comPoseDelete()
end
card_50_s2s_300_resolve = function()
    local card_50_s2s_300_intro, card_50_s2s_300_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(2864, "NONVOICE", "【直哉】「あれ？」")
    vms(2865, "NONVOICE", "【彩野】「どうかしたの、直哉くん」")
    vms(2866, "NONVOICE", "【直哉】「うん。ここで消しゴムを見て約束を思い出すと言うことは、このセクション２のお話って、セクション１の前になるのかな？」")
    vms(2867, "NONVOICE", "【彩野】「うーん、そうとも言い切れない感じがする。はっきり前、って言い切ってる部分があるわけでもないし……」")
    vms(2868, "NONVOICE", "【直哉】「ふむ……」")
    vms(2869, "NONVOICE", "【直哉】「と、言うことは、この箇所も物語が『繋がっている』事を示している描写になるのかな」")
    vms(2870, "NONVOICE", "【彩野】「うん。そうかもしれない」")
    vms(2871, "NONVOICE", "消しゴム。セクション１に続いてまた出てきたと言うことは、この道具が物語の何かのキーになっているということなのだろうか？")
    vms(2872, "NONVOICE", "もしかしたらまたどこかの『物語』で、消しゴムが出てくるのかもしれない。")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『消しゴムに名前』のあらすじを作成しました。") -- tr_line:26
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[5].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_50_s2s_300_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 5 then
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
            vms(2873, "NONVOICE", "確か、約束をしている場面だったかな……。")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_50_s2s_300_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end