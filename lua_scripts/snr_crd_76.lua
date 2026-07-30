local card_76_s3s_301_intro, card_76_s3s_301_resolve, v2, v3, v4, v5
card_76_s3s_301_intro = function()
    local card_76_s3s_301_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(3432, "NONVOICE", "【直哉】「廊下で見かけたユウイチを放っておく場面、だね」")
    vms(3433, "NONVOICE", "【直哉】「それでね、彩野さん」")
    vms(3434, "NONVOICE", "【直哉】「もう一つの選択肢――『後をつける』場面のあらすじをつくる時にも考えたんだけど――」")
    vms(3435, "NONVOICE", "【直哉】「ここの場面って、他の物語……『セクション２』に登場した場面と似ているなって思ったんだ」")
    comPoseLoad("po2_aya_f_2_a")
    vms(3436, "NONVOICE", "【彩野】「ふむふむ……」")
    vms(3437, "NONVOICE", "【直哉】「それで、『後をつける』展開の先は嫌な予感がするから、この『ほうっておく』展開を選んだんだ」")
    vms(3438, "NONVOICE", "【彩野】「えっと、つまり……」")
    comPoseLoad("po2_aya_f_1_a")
    vms(3439, "NONVOICE", "【彩野】「この場面の展開は『セクション２と似ていて』、選ぶ展開によっては『嫌な予感がする』ということ？」")
    vms(3440, "NONVOICE", "【直哉】「うん、そういう事になるかな」")
    vms(3441, "NONVOICE", "【彩野】「うーん、セクション２の展開を見て、嫌な予感、か……」")
    vms(3442, "NONVOICE", "【彩野】「直哉くん、その、『セクション２』の物語というので、『廊下でユウイチを見かけて嫌な展開』になった場面って、なにかある？」")
    vms(3443, "NONVOICE", "【直哉】「あ、うん……。一応……」")
    comPoseDelete()
end
card_76_s3s_301_resolve = function()
    local card_76_s3s_301_intro, card_76_s3s_301_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(3444, "NONVOICE", "【彩野】「……」")
    comPoseLoad("po2_aya_f_2_e")
    vms(3445, "NONVOICE", "【彩野】「そっか、屋上から……」")
    vms(3446, "NONVOICE", "【直哉】「彩野さん……」")
    vms(3447, "NONVOICE", "【彩野】「ありがとう、直哉くん……」")
    vms(3448, "NONVOICE", "【彩野】「……うん」")
    vms(3449, "NONVOICE", "彩野さんは、自分自身に言い聞かせるように頷いた。")
    comPoseLoad("po2_aya_f_1_c")
    vms(3450, "NONVOICE", "【彩野】「ここは、ほうっておく展開がいいのかもしれないね。次の物語に進んでいい？」")
    vms(3451, "NONVOICE", "【直哉】「あ、うん……」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『ほうっておく』のあらすじを作成しました。") -- tr_line:37
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[57].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_76_s3s_301_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 57 then
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
            vms(3452, "NONVOICE", "セクション２、廊下でユウイチを見かけた場面のあらすじは『ユウイチの後ろ姿』『夜の廊下』")
            vms(3453, "NONVOICE", "良い結末だったのは『夜の廊下』だから……。")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_76_s3s_301_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end