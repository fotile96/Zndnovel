local card_151_s4s_70_intro, card_151_s4s_70_resolve, v2, v3, v4, v5
card_151_s4s_70_intro = function()
    local card_151_s4s_70_intro
    cPlayBGMWrap(cGetFileName("bgm", "bgm_5_x"))
    comPoseLoad("po2_aya_f_1_a")
    vms(945, "NONVOICE", "【直哉】「ユウイチがメモの事をユカリ先生に聞く場面、だね」")
    vms(946, "NONVOICE", "【彩野】「メモの事はユカリ先生は知らなかったみたいなんだけど、このシーンの終わりで――」")
    comPoseLoad("po2_aya_f_2_d")
    vms(947, "NONVOICE", "【彩野】「どうしてユカリ先生が手なんか回す必要があったんだろう？」")
    vms(948, "NONVOICE", "【直哉】「それは――」")
    vms(949, "NONVOICE", "……この場面は、セクション３で、ユウイチとユカリ先生が抱き合っていた場面と、『繋がっている』ことは間違いない。")
    vms(950, "NONVOICE", "でも、その場面を『あらすじ』として彩野さんに教えてしまっていいものだろうか？")
    vms(951, "NONVOICE", "……。")
    vms(952, "NONVOICE", "……ここは……。")
    vms(953, "NONVOICE", "……隠しても、仕方ない。そう思う。")
    vms(954, "NONVOICE", "この場面を理解するには、図書室のシーンを知る必要があるのは明らかだから。")
    comPoseDelete()
end
card_151_s4s_70_resolve = function()
    local card_151_s4s_70_intro, card_151_s4s_70_resolve
    oCard.cardAnswerTrue()
    comPoseLoad("po2_aya_f_2_c")
    vms(955, "NONVOICE", "【彩野】「……え……」")
    comPoseLoad("po2_aya_f_2_e")
    vms(956, "NONVOICE", "【彩野】「……」")
    comPoseLoad("po2_aya_f_1_c")
    vms(957, "NONVOICE", "【彩野】「あ、そうなんだ……」")
    vms(958, "NONVOICE", "【直哉】「そう。このカードに書かれているみたいに――」")
    vms(959, "NONVOICE", "【直哉】「セクション３で、アヤノさんは『ユカリ先生とユウイチが抱き合っている』場面を目撃しているんだ」")
    vms(960, "NONVOICE", "【彩野】「だから、ユカリ先生はこんな風に、ユウイチに……」")
    vms(961, "NONVOICE", "【彩野】「……う、うん……」")
    comPoseLoad("po2_aya_f_1_a")
    vms(962, "NONVOICE", "【彩野】「……わかった」")
    vms(963, "NONVOICE", "【彩野】「……あらすじ、まとめる……ね」")
    cLoadPlaySE(cGetFileName("se", "se_30"), false)
    oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『図書室の先生』のあらすじを作成しました。") -- tr_line:36
    comPoseDelete()
    vms(964, "NONVOICE", "【直哉】「……」")
    comPoseDelete()
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
main = function()
    local v2, v3, v4, v5, v6
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[80].hold == -1 then
        oCard.mesNot()
        comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    card_151_s4s_70_intro()
    v2 = 0
    v3 = 0
    v4 = -1
    while v2 < 1 do
        v5 = oCard.selectCardObj()
        if v5 == 80 then
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
            vms(965, "NONVOICE", "彩野さんにセクション３、『図書室で目撃』した場面を教えよう……。")
            comPoseDelete()
        end
        if v3 == 0 then
            oCard.mesNG()
            v3 = v3 + 1
            comPoseDelete()
        end
        wait(30)
    end
    card_151_s4s_70_resolve()
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end