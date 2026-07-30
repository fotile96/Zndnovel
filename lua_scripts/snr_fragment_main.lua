local v0, v1, v2, v3, v4, v5, v6, v7, v8, v9, v10, v11, v12, v13, v14, v15, v16, v17, v18, v19, v20, v21, v22, v23
v0 = function(p0)
    local v0 = true
    local v1 = 1
    local v2, v3, i2, v4
    v2 = p0 - 1
    v3 = 1
    for i2 = v1, v2, v3 do
        v4 = string.sub(gameSave.storyRoute[i2].sceneId, -4)
        if not (v4 == "_sel") then
            if gameSave.myCard[sceneId2aCard[gameSave.storyRoute[i2].sceneId]].hold == -1 then
                v0 = false
            end
        end
    end
    return v0
end
v1 = function(p0, p1)
    local v0 = 0
    local v1 = 0
    local v2 = 2
    local v3 = 0
    local v4, v5, v6, v7, v8, v9, v10, v11, v12, v13, v14, v15, v16, i16, v17, v18, v19, v20, v21, v22, v23
    v4 = p0 - p1
    if (not (p0 == p1)) and (v4 < 2) and (-2 < v4) then
        v3 = 10
    end
    v5 = 0
    v6 = 0
    v7 = 0
    v8 = 0
    v9 = 0
    v10 = 0
    v11 = 0
    v12 = 0
    v13 = 0
    v14 = layerName.plot - 2
    v15 = layerName.plot + 50
    v16 = 1
    for i16 = v14, v15, v16 do
        layerLoad(i16, "")
    end
    if not (p0 == 1) then
        layerCopy((layerName.plot + 40), layerName.sys_2_d)
        layerClip((layerName.plot + 40), 0, 0, 30, 15)
        layerPosition((layerName.plot + 40), 5, 80)
    end
    v14 = comSectionStoryGetCount()
    if not (p0 == v14) then
        layerCopy((layerName.plot + 41), layerName.sys_2_d)
        layerClip((layerName.plot + 41), 30, 0, 60, 15)
        layerPosition((layerName.plot + 41), 449, 80)
    end
    v14 = sceneId2aCard[gameSave.storyRoute[p0].sceneId]
    layerCopy(layerName.cardLabel1, sceneState[v14].layerName)
    layerClip(layerName.cardLabel1, sceneState[v14].clipX, sceneState[v14].clipY, (sceneState[v14].clipX + 145), (sceneState[v14].clipY + 15))
    layerPosition(layerName.cardLabel1, 330, 5)
    v15 = (comSectionStoryGetCount()) - 2
    if (p0 < v15) and (v4 == -1) then
        v5 = 80
        v7 = 372
        plotLayerPositionX2 = 409
        v9 = 103
        v11 = 100
        v6 = 70
        v8 = 386
        plotLayerMovePositionX2 = 419
        v10 = 100
        v12 = 0
        v13 = p0 + 3
    elseif (3 < p0) and (v4 == 1) then
        v5 = 80
        v7 = 29
        plotLayerPositionX2 = 65
        v9 = 103
        v11 = 100
        v6 = 70
        v8 = 9
        plotLayerMovePositionX2 = 50
        v10 = 100
        v12 = 0
        v13 = p0 - 3
    end
    if not (v13 == 0) then
        v15 = sceneId2aCard[gameSave.storyRoute[v13].sceneId]
        layerCopy((layerName.plot - 1), plotState[v15].layerName)
        layerClip((layerName.plot - 1), plotState[v15].clipX, plotState[v15].clipY, (plotState[v15].clipX + 82), (plotState[v15].clipY + 48))
        v16 = string.sub(gameSave.storyRoute[v13].sceneId, -4)
        if v16 == "_sel" then
            layerCopy((layerName.plot - 2), layerName.sys_2_c)
            if gameSave.myCard[v15].hold == -1 then
                if v2 == 2 then
                    layerClip((layerName.plot - 2), 0, 133, 83, 152)
                else
                    layerClip((layerName.plot - 2), 0, 114, 83, 133)
                end
            elseif v2 == 2 then
                layerClip((layerName.plot - 2), 0, 57, 83, 76)
            else
                layerClip((layerName.plot - 2), 0, 38, 83, 57)
            end
        else
            layerCopy((layerName.plot - 2), layerName.sys_2_b)
            if gameSave.myCard[v15].hold == -1 then
                if v2 == 2 then
                    layerClip((layerName.plot - 2), 0, 133, 83, 152)
                else
                    layerClip((layerName.plot - 2), 0, 114, 83, 133)
                end
            elseif v2 == 2 then
                layerClip((layerName.plot - 2), 0, 57, 83, 76)
            else
                layerClip((layerName.plot - 2), 0, 38, 83, 57)
            end
        end
        layerScale((layerName.plot - 1), v5, v5)
        layerScale((layerName.plot - 2), v5, v5)
        layerMoveScale((layerName.plot - 1), v6, v6, v3)
        layerMoveScale((layerName.plot - 2), v6, v6, v3)
        layerPosition((layerName.plot - 1), v7, 60)
        layerPosition((layerName.plot - 2), v7, v9)
        layerMovePosition((layerName.plot - 1), v8, 60, v3)
        layerMovePosition((layerName.plot - 2), v8, v10, v3)
        layerAlpha((layerName.plot - 1), v11)
        layerAlpha((layerName.plot - 2), v11)
        layerMoveAlpha((layerName.plot - 1), v12, v3)
        i16 = layerName.plot - 2
        v20 = v12
        layerMoveAlpha(i16, v20, v3)
    end
    if 2 < p0 then
        p0 = p0 - 2
        v2 = 0
    elseif 1 < p0 then
        p0 = p0 - 1
        v2 = 1
    end
    v15 = 0
    v16 = 4
    i16 = 1
    for v20 = v15, v16, i16 do
        v18 = p0 + v20
        if gameSave.storyRoute[v18].sceneId == -1 then
            break
        end
        v19 = p0 + v20
        v17 = sceneId2aCard[gameSave.storyRoute[v19].sceneId]
        layerCopy((layerName.plot + (v20 * 3)), plotState[v17].layerName)
        layerClip((layerName.plot + (v20 * 3)), plotState[v17].clipX, plotState[v17].clipY, (plotState[v17].clipX + 82), (plotState[v17].clipY + 48))
        v18 = string.sub(gameSave.storyRoute[(p0 + v20)].sceneId, -4)
        if v18 == "_sel" then
            v19 = layerName.plot
            v21 = v20 * 3
            v19 = (v19 + v21) + 1
            layerCopy(v19, layerName.sys_2_c)
            if gameSave.myCard[v17].hold == -1 then
                if v2 == 2 then
                    v19 = layerName.plot
                    v21 = v20 * 3
                    v19 = (v19 + v21) + 1
                    layerClip(v19, 0, 133, 83, 152)
                else
                    v19 = layerName.plot
                    v21 = v20 * 3
                    v19 = (v19 + v21) + 1
                    layerClip(v19, 0, 114, 83, 133)
                end
            elseif v2 == 2 then
                v19 = layerName.plot
                v21 = v20 * 3
                v19 = (v19 + v21) + 1
                layerClip(v19, 0, 57, 83, 76)
            else
                v19 = layerName.plot
                v21 = v20 * 3
                v19 = (v19 + v21) + 1
                layerClip(v19, 0, 38, 83, 57)
            end
        else
            v19 = layerName.plot
            v21 = v20 * 3
            v19 = (v19 + v21) + 1
            layerCopy(v19, layerName.sys_2_b)
            if gameSave.myCard[v17].hold == -1 then
                if v2 == 2 then
                    v19 = layerName.plot
                    v21 = v20 * 3
                    v19 = (v19 + v21) + 1
                    layerClip(v19, 0, 133, 83, 152)
                else
                    v19 = layerName.plot
                    v21 = v20 * 3
                    v19 = (v19 + v21) + 1
                    layerClip(v19, 0, 114, 83, 133)
                end
            elseif v2 == 2 then
                v19 = layerName.plot
                v21 = v20 * 3
                v19 = (v19 + v21) + 1
                layerClip(v19, 0, 57, 83, 76)
            else
                v19 = layerName.plot
                v21 = v20 * 3
                v19 = (v19 + v21) + 1
                layerClip(v19, 0, 38, 83, 57)
            end
        end
        if v2 == 0 then
            if 0 < v4 then
                v5 = 90
                v18 = (v2 + 1) * 95
                v7 = v18 + 14
                v18 = ((v2 + 1) * 95) + 55
                plotLayerPositionX2 = v18
                v9 = 106
                v11 = 100
            elseif v4 < 0 then
                v5 = 70
                v18 = v2 * 95
                v7 = v18 + 9
                v18 = (v2 * 95) + 50
                plotLayerPositionX2 = v18
                v9 = 100
                v11 = 0
            end
            v6 = 80
            v18 = v2 * 95
            v8 = v18 + 29
            v18 = (v2 * 95) + 65
            plotLayerMovePositionX2 = v18
            v10 = 103
            v12 = 100
        elseif v2 == 1 then
            if 0 < v4 then
                v5 = 100
                v18 = (v2 + 1) * 95
                v7 = v18 + 9
                v18 = ((v2 + 1) * 95) + 50
                plotLayerPositionX2 = v18
                v9 = 109
                v11 = 100
            elseif v4 < 0 then
                v5 = 80
                v18 = (v2 - 1) * 95
                v7 = v18 + 29
                v18 = ((v2 - 1) * 95) + 65
                plotLayerPositionX2 = v18
                v9 = 103
                v11 = 100
            end
            v6 = 90
            v18 = v2 * 95
            v8 = v18 + 14
            v18 = (v2 * 95) + 55
            plotLayerMovePositionX2 = v18
            v10 = 106
            v12 = 100
        elseif v2 == 2 then
            if 0 < v4 then
                v18 = (v2 + 1) * 95
                v7 = v18 + 4
                v18 = ((v2 + 1) * 95) + 45
                plotLayerPositionX2 = v18
            elseif v4 < 0 then
                v18 = (v2 - 1) * 95
                v7 = v18 + 14
                v18 = ((v2 - 1) * 95) + 55
                plotLayerPositionX2 = v18
            end
            v9 = 106
            v5 = 90
            v11 = 100
            v6 = 100
            v18 = v2 * 95
            v8 = v18 + 9
            v18 = (v2 * 95) + 50
            plotLayerMovePositionX2 = v18
            v10 = 109
            v12 = 100
        elseif v2 == 3 then
            if 0 < v4 then
                v5 = 80
                v18 = (v2 + 1) * 95
                v7 = v18 - 8
                v18 = ((v2 + 1) * 95) + 29
                plotLayerPositionX2 = v18
                v9 = 103
                v11 = 100
            elseif v4 < 0 then
                v5 = 100
                v18 = (v2 - 1) * 95
                v7 = v18 + 9
                v18 = ((v2 - 1) * 95) + 50
                plotLayerPositionX2 = v18
                v9 = 109
                v11 = 100
            end
            v6 = 90
            v18 = v2 * 95
            v8 = v18 + 4
            v18 = (v2 * 95) + 45
            plotLayerMovePositionX2 = v18
            v10 = 106
            v12 = 100
        elseif v2 == 4 then
            if 0 < v4 then
                v5 = 70
                v7 = v2 * 95
                v18 = (v2 * 95) + 33
                plotLayerPositionX2 = v18
                v9 = 100
                v11 = 0
            elseif v4 < 0 then
                v5 = 90
                v18 = (v2 - 1) * 95
                v7 = v18 + 4
                v18 = ((v2 - 1) * 95) + 45
                plotLayerPositionX2 = v18
                v9 = 106
                v11 = 100
            end
            v6 = 80
            v18 = v2 * 95
            v8 = v18 - 8
            v18 = (v2 * 95) + 29
            plotLayerMovePositionX2 = v18
            v12 = 100
            v10 = 103
        end
        layerScale((layerName.plot + (v20 * 3)), v5, v5)
        v19 = layerName.plot
        v21 = v20 * 3
        v19 = (v19 + v21) + 1
        layerScale(v19, v5, v5)
        layerMoveScale((layerName.plot + (v20 * 3)), v6, v6, v3)
        v19 = layerName.plot
        v21 = v20 * 3
        v19 = (v19 + v21) + 1
        layerMoveScale(v19, v6, v6, v3)
        layerPosition((layerName.plot + (v20 * 3)), v7, 60)
        v19 = layerName.plot
        v21 = v20 * 3
        v19 = (v19 + v21) + 1
        layerPosition(v19, v7, v9)
        layerMovePosition((layerName.plot + (v20 * 3)), v8, 60, v3)
        v19 = layerName.plot
        v21 = v20 * 3
        v19 = (v19 + v21) + 1
        layerMovePosition(v19, v8, v10, v3)
        layerAlpha((layerName.plot + (v20 * 3)), v11)
        v19 = layerName.plot
        v21 = v20 * 3
        v19 = (v19 + v21) + 1
        layerAlpha(v19, v11)
        layerMoveAlpha((layerName.plot + (v20 * 3)), v12, v3)
        v19 = layerName.plot
        v21 = v20 * 3
        v19 = (v19 + v21) + 1
        layerMoveAlpha(v19, v12, v3)
        v1 = v1 + 1
        v2 = v2 + 1
        if 5 <= v1 then
            break
        end
        if v2 == 5 then
            break
        end
    end
end
v2 = function()
    local v0, v2
    savedataTitle("フラグメントモード", "")
    wait(1)
    cInitGame()
    layerCopy(layerName.bg1, layerName.bg_1_a_0)
    layerCopy((layerName.bg1 + 1), layerName.sys_3_a)
    layerClip((layerName.bg1 + 1), 0, 0, 160, 37)
    layerPosition((layerName.bg1 + 1), 5, 5)
    layerCopy((layerName.bg1 + 2), layerName.sys_3_a)
    layerClip((layerName.bg1 + 2), 0, 40, 160, 120)
    layerPosition((layerName.bg1 + 2), 195, 56)
    layerCopy((layerName.bg1 + 3), layerName.sys_3_a)
    layerClip((layerName.bg1 + 3), 0, 120, 160, 191)
    layerPosition((layerName.bg1 + 3), 338, 191)
    v1(selectItemNo, selectItemNo)
    layerLoadAsync(0, layerName.card1, cGetFileName("card", "crd_1_a"))
    wait(1)
end
main = function()
    local v3, v4, v5, v6, v7, v8, v9, v10, v11, v12, v13, v14, v15, i10, v16, v17, v18, v19, v20
    advPart(false)
    logEnable(false)
    systemConfig.unsetConfigButton()
    v3 = comSectionStoryGetCount()
    if v3 == 0 then
        vms(6056, "NONVOICE", "【■おしらせ】あらすじを作成する物語がありません。_rストーリーモードをプレイしてください。")
        cInitGame()
        run(cGetFileName("script", "snr_mainmenu"))
        quit()
    end
    if gameSave.myCard[136].hold == 1 then
        if gameSave.myCard[145].hold == -1 then
            cInitGame()
            doScriptScene = "s3fc-10"
            run(cGetFileName("script", "snr_s3_10_fc"))
            quit()
        end
    end
    if gameSave.tutorial.firstFragment == 0 then
        if gameSave.tutorial.firstFragmentBegin == 0 then
            systemConfig.setConfigButton()
            run(cGetFileName("script", "snr_crd_0"))
            quit()
        else
            gameSave.storyRoute[1].sceneId = "s1s_20"
            gameSave.storyRoute[1].ayanoTime = 0
        end
    end
    if selectItemNo < 1 then
        selectItemNo = v3
    end
    if v3 < selectItemNo then
        selectItemNo = v3
    end
    v2()
    v4 = false
    v5 = 0
    v6 = false
    v7 = selectItemNo
    v8 = v7
    v9 = false
    v10 = 1
    v11 = 1
    v12 = 1
    systemConfig.setConfigButton()
    while true do
        v13 = pressButton("RIGHT")
        if (v13 == true) and (v9 == false) and (v7 < v3) then
            v8 = v7
            v13 = v7 + 1
            if v3 < v13 then
                v7 = v3
            else
                v7 = v7 + 1
            end
            v9 = true
        end
        v13 = pressButton("LEFT")
        if (v13 == true) and (v9 == false) and (1 < v7) then
            v8 = v7
            v7 = v7 - 1
            v9 = true
        end
        v13 = pressButton("R")
        if (v13 == true) and (v9 == false) then
            v8 = v7
            v13 = v7 + 1
            v14 = v3
            v15 = 1
            for i10 = v13, v14, v15 do
                v16 = sceneId2aCard[gameSave.storyRoute[i10].sceneId]
                v7 = i10
                if gameSave.myCard[v16].hold == -1 then
                    v7 = i10
                    break
                end
            end
            wait(5)
            v9 = true
        end
        v13 = pressButton("L")
        if (v13 == true) and (v9 == false) then
            v8 = v7
            v13 = v7 - 1
            v14 = 1
            v15 = -1
            for i10 = v13, v14, v15 do
                v16 = sceneId2aCard[gameSave.storyRoute[i10].sceneId]
                v7 = i10
                if gameSave.myCard[v16].hold == -1 then
                    v7 = i10
                    break
                end
            end
            wait(5)
            v9 = true
        end
        if v9 == true then
            keyPlaySE(seName.arrowKey)
            fontClear()
            v1(v7, v8)
            v5 = 0
            v9 = false
            layerLoad(layerName.card1, "")
            wait(3)
        end
        v13 = sceneId2aCard[gameSave.storyRoute[v7].sceneId]
        if (not (gameSave.myCard[v13].hold == -1)) and (v5 <= 3) then
            if 3 <= v5 then
                layerLoadAsync(0, layerName.card1, cGetFileName("card", "crd_" .. v13 .. "_a"))
                v6 = true
            end
            v14 = v5 + 1
            if 4 < v14 then
                v5 = 4
            else
                v5 = v5 + 1
            end
        end
        if v6 == true then
            v14 = layerIsLoad(layerName.card1)
            if v14 == true then
                layerVisible(layerName.card1, true)
                layerAlpha(layerName.card1, 0)
                layerPosition(layerName.card1, 130, 110)
                layerMovePosition(layerName.card1, 130, 130, 10)
                layerMoveAlpha(layerName.card1, 100, 10)
                v6 = false
            end
        end
        v14 = pressButton("CIRCLE")
        if not (v14 == true) then
            v10 = 0
        end
        v14 = pressButton("CIRCLE")
        if (v14 == true) and (v9 == false) and (v10 == 0) then
            v14 = string.sub(gameSave.storyRoute[v7].sceneId, -4)
            if not (v14 == "_sel") then
                v14 = sceneId2aCard[gameSave.storyRoute[v7].sceneId]
                if gameSave.myCard[v14].hold == -1 then
                    v15 = v0(v7)
                    if v15 == false then
                        oCard.mesNotStoryLine()
                    else
                        keyPlaySE(seName.circle)
                        wait(10)
                        selectItemNo = v7
                        gameSave.fragmentDoSceneId = gameSave.storyRoute[v7].sceneId
                        gameSave.fragmentDoCardId = v14
                        fontClear()
                        run(cGetFileName("scriptc", "snr_crd_" .. v14))
                        quit()
                    end
                else
                    v15 = cGetFileName("sysgim", "sys_5_f")
                    keyPlaySE(seName.circle)
                    i10 = comDlgYesNoSel(v15, 0, 50, 1)
                    if i10 == true then
                        wait(10)
                        selectItemNo = v7
                        gameSave.fragmentDoSceneId = gameSave.storyRoute[v7].sceneId
                        gameSave.fragmentDoCardId = v14
                        fontClear()
                        run(cGetFileName("scriptc", "snr_crd_" .. v14))
                        quit()
                    else
                        v10 = 1
                        v11 = 1
                        v12 = 1
                    end
                end
            else
                v14 = sceneId2aCard[gameSave.storyRoute[v7].sceneId]
                if gameSave.myCard[v14].hold == -1 then
                    keyPlaySE(seName.circle)
                    wait(10)
                    selectItemNo = v7
                    gameSave.fragmentDoSceneId = gameSave.storyRoute[v7].sceneId
                    gameSave.fragmentDoCardId = v14
                    fontClear()
                    run(cGetFileName("scriptc", "snr_crd_" .. v14))
                    quit()
                else
                    v15 = cGetFileName("sysgim", "sys_5_f")
                    keyPlaySE(seName.circle)
                    if comDlgYesNoSel(v15, 0, 0, 1) == true then
                        wait(10)
                        selectItemNo = v7
                        gameSave.fragmentDoSceneId = gameSave.storyRoute[v7].sceneId
                        gameSave.fragmentDoCardId = v14
                        fontClear()
                        run(cGetFileName("scriptc", "snr_crd_" .. v14))
                        quit()
                    else
                        v10 = 1
                        v11 = 1
                        v12 = 1
                    end
                end
            end
        end
        v14 = pressButton("CROSS")
        if not (v14 == true) then
            v11 = 0
        end
        if (pressButton("CROSS") == true) and (v11 == 0) then
            systemConfig.unsetConfigButton()
            keyPlaySE(seName.cross)
            break
        else
            if not (pressButton("TRIANGLE") == true) then
                v12 = 0
            end
            if (pressButton("TRIANGLE") == true) and (v12 == 0) then
                systemConfig.unsetConfigButton()
                keyPlaySE(seName.cross)
                layerCopy(199, layerName.effectBlack)
                fontClear()
                switchScreen(0, "", 60)
                selectItemNo = v7
                comSectionFragmentItemInit()
                cInitGame()
                run(cGetFileName("script", "snr_story_main"))
                quit()
            end
            wait(2)
        end
    end
    wait(1)
    layerCopy(199, layerName.effectBlack)
    fontClear()
    switchScreen(0, "", 30)
    cInitGame()
    run(cGetFileName("script", "snr_mainmenu"))
    quit()
end