local card_146_s4s_10_intro, card_146_s4s_10_resolve, v2, v3, v4, v5
card_146_s4s_10_intro = function()
    local card_146_s4s_10_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(729, "NONVOICE", "【彩野】「あ、直哉くん、ちょっといい？」")
    vms(730, "NONVOICE", "【直哉】「どうかした？」")
    comPoseLoad("po2_aya_f_2_a")
    vms(731, "NONVOICE", "【彩野】「えっとね、このユウイチと会ったシーンって、どの『選択肢』からの分岐になるんだっけ？」")
    vms(732, "NONVOICE", "【直哉】「あ、それはね、セクション３の――」")
    comPoseDelete()
end
card_146_s4s_10_resolve = function()
    local card_146_s4s_10_intro, card_146_s4s_10_resolve, v2, v3
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(733, "NONVOICE", "【彩野】「そっか、廊下でユウイチを見かけて――」")
    comPoseLoad("po2_aya_f_2_e")
    vms(734, "NONVOICE", "【彩野】「メモを――」")
    vms(735, "NONVOICE", "【直哉】「どうかした？ 彩野さん」")
    wait(1)
    layerLoad(layerName.pose3, cGetFileName("cutin", "cut_61"))
    layerPosition(layerName.pose3, 320, 30)
    switchScreen(0, "", 30)
    wait(30)
    comPoseLoad("po2_aya_f_1_a")
    vms(736, "NONVOICE", "【彩野】「うん……実はね、あのメモの文面、私も見たような気がして」")
    vms(737, "NONVOICE", "【直哉】「え？ 『現実』に？」")
    vms(738, "NONVOICE", "【彩野】「うん。いつ、どこで見たのかははっきりしないんだけど……」")
    vms(739, "NONVOICE", "『誰も見た事のない夕焼けの秘密は、屋上に行けばわかる』")
    wait(1)
    layerLoad(layerName.pose3, "")
    switchScreen(0, "", 30)
    wait(30)
    vms(740, "NONVOICE", "メモを、現実に彩野さんが見た？")
    cPlayOneshotMusic(cGetFileName("mus", "mus_13"))
    vms(741, "NONVOICE", "これは……かなり重要な情報ではないのだろうか？")
    vms(742, "NONVOICE", "もしかしたら、あのメモの文言は『現実』に彩野さんが屋上から飛び降りた事と――")
    vms(743, "NONVOICE", "なにか関係があるという事なのだろうか？")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『ポケットの中のメモ』のあらすじを作成しました。") -- tr_line:41
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[75].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_146_s4s_10_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 75 then
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
            vms(744, "NONVOICE", "このシーンは、セクション３で、ユウイチを見かけた所から分岐した場面だ。")
            vms(745, "NONVOICE", "その分岐のシーン名は、『ユウイチの――』。")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_146_s4s_10_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end