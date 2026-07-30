local card_73_s3s_190_intro, card_73_s3s_190_resolve, v2, v3, v4, v5
card_73_s3s_190_intro = function()
    local card_73_s3s_190_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(3360, "NONVOICE", "【直哉】「真剣に階段のウワサについて聞く場面、だね」")
    vms(3361, "NONVOICE", "【直哉】「オマジナイの次は、階段のウワサ……」")
    vms(3362, "NONVOICE", "【直哉】「両方ともふざけないで『真剣に聞く』事が、展開を進めるための条件になっている、のかな」")
    comPoseLoad("po2_aya_f_2_a")
    vms(3363, "NONVOICE", "【彩野】「オマジナイ？ そういう物語もあるんだね」")
    vms(3364, "NONVOICE", "【直哉】「あ、そっか。展開が似てるなら、セクション２の『物語』も、参考にしてもらった方がいいかもしれない」")
    vms(3365, "NONVOICE", "【直哉】「セクション２のあらすじは――」")
    comPoseDelete()
end
card_73_s3s_190_resolve = function()
    local card_73_s3s_190_intro, card_73_s3s_190_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_1_a")
    vms(3366, "NONVOICE", "【彩野】「ふむ、オマジナイ……かあ」")
    vms(3367, "NONVOICE", "【直哉】「うん。『セクション２』の物語」")
    comPoseLoad("po2_aya_f_2_c")
    vms(3368, "NONVOICE", "【彩野】「あ、セクション２があると言うことは、１もあるんだよね？」")
    vms(3369, "NONVOICE", "【直哉】「そう。『セクション１』の物語は、『コックリさん』だった」")
    comPoseLoad("po2_aya_f_1_c")
    vms(3370, "NONVOICE", "【彩野】「……コックリさん。そうなんだ……」")
    comPoseLoad("po2_aya_f_1_a")
    vms(3371, "NONVOICE", "【彩野】「うーん、コックリさん、オマジナイ、階段の幽霊っぽいウワサ」")
    vms(3372, "NONVOICE", "【直哉】「なんというか、王道の展開ではあるよね」")
    comPoseLoad("po2_aya_f_2_e")
    vms(3373, "NONVOICE", "【彩野】「うん……」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『真剣に聞く』のあらすじを作成しました。") -- tr_line:32
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[134].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_73_s3s_190_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 134 then
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
            vms(3374, "NONVOICE", "セクション２のあらすじを参考にしてもらおう。")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_73_s3s_190_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end