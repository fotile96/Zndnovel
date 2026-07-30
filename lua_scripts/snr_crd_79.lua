local card_79_s3s_360_intro, card_79_s3s_360_resolve, v2, v3, v4, v5
card_79_s3s_360_intro = function()
    local card_79_s3s_360_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(3491, "NONVOICE", "【直哉】「廊下でユウイチを見かけて、後をつける場面、だね」")
    vms(3492, "NONVOICE", "【直哉】「それで彩野さん、もしかしたら、なんだけど……」")
    vms(3493, "NONVOICE", "【彩野】「ん？ どうかしたの、直哉くん」")
    vms(3494, "NONVOICE", "【直哉】「うん。えっとね、他の『物語』でも――」")
    vms(3495, "NONVOICE", "【直哉】「こんな風に『学校をふらついて歩いている』ユウイチを見かけるシーンがあったんだ」")
    vms(3496, "NONVOICE", "【彩野】「えっと、どんな感じ？」")
    vms(3497, "NONVOICE", "セクション２、廊下を歩いていたユウイチのあらすじを見せればいいと思うけど――")
    vms(3498, "NONVOICE", "バッドエンドになる方の『あらすじ』は止めた方がいいだろうな……やっぱり。")
    comPoseDelete()
end
card_79_s3s_360_resolve = function()
    local card_79_s3s_360_intro, card_79_s3s_360_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_2_a")
    vms(3499, "NONVOICE", "【彩野】「ふむ……。となると、この場面はセクション２と関係しているってことになるよね」")
    vms(3500, "NONVOICE", "【直哉】「うーん。そこまでは言い切れないけど。まだお話も途中だからね」")
    comPoseLoad("po2_aya_f_1_a")
    vms(3501, "NONVOICE", "【彩野】「あ……。そうだよね」")
    vms(3502, "NONVOICE", "【直哉】「でも、『お話の繋がり』は気になるよね。これまで読んできた物語でも、所々でお話が繋がっていることはあったから」")
    vms(3503, "NONVOICE", "【直哉】「何かしらの関連はある――その可能性は高いと思う」")
    vms(3504, "NONVOICE", "【彩野】「うん……」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『後をつける』のあらすじを作成しました。") -- tr_line:28
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[58].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_79_s3s_360_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 58 then
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
            vms(3505, "NONVOICE", "セクション２、夜の廊下を歩くユウイチの場面を見せてみよう。")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_79_s3s_360_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end