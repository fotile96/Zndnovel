local v0, v1, v2, v3, v4, v5, v6, v7, v8, v9, v10, v11, v12, v13, v14, v15, v16, v17, v18, v19, v20, v21, v22, v23, v24, v25, v26, v27
v0 = function(p0, p1)
    local v0
    if 90 <= p1 then
        layerClip(p0, 0, 180, 75, 200)
    elseif 80 <= p1 then
        layerClip(p0, 0, 160, 75, 180)
    elseif 70 <= p1 then
        layerClip(p0, 0, 140, 75, 160)
    elseif 60 <= p1 then
        layerClip(p0, 0, 120, 75, 140)
    elseif 50 <= p1 then
        layerClip(p0, 0, 100, 75, 120)
    elseif 40 <= p1 then
        layerClip(p0, 0, 80, 75, 100)
    elseif 30 <= p1 then
        layerClip(p0, 0, 60, 75, 80)
    elseif 20 <= p1 then
        layerClip(p0, 0, 40, 75, 60)
    elseif 10 <= p1 then
        layerClip(p0, 0, 20, 75, 40)
    else
        layerClip(p0, 0, 0, 75, 20)
    end
end
v1 = function(p0, p1)
    local v1 = 0
    local v2 = 0
    local v3 = 2
    local v4 = 0
    local v5, v6, v7, v8, v9, v10, v11, v12, v13, v14, v15, v16, v17, v18, v19, i18, v20, v21, v22, v23, v24, v25, v26, v27
    v5 = p0 - p1
    if (not (p0 == p1)) and (v5 < 2) and (-2 < v5) then
        v4 = 10
    end
    v6 = 0
    v7 = 0
    v8 = 0
    v9 = 0
    v10 = 0
    v11 = 0
    v12 = 0
    v13 = 0
    v14 = 0
    v15 = 0
    v16 = 0
    v17 = layerName.plot - 4
    v18 = layerName.plot + 50
    v19 = 1
    for i18 = v17, v18, v19 do
        layerLoad(i18, "")
    end
    if not (p0 == 1) then
        layerCopy((layerName.plot + 40), layerName.sys_2_d)
        layerClip((layerName.plot + 40), 0, 0, 30, 15)
        layerPosition((layerName.plot + 40), 5, 80)
    end
    v17 = comSectionStoryGetCount()
    if not (p0 == v17) then
        layerCopy((layerName.plot + 41), layerName.sys_2_d)
        layerClip((layerName.plot + 41), 30, 0, 60, 15)
        layerPosition((layerName.plot + 41), 449, 80)
    end
    v17 = sceneId2aCard[gameSave.storyRoute[p0].sceneId]
    layerCopy(layerName.cardLabel1, sceneState[v17].layerName)
    layerClip(layerName.cardLabel1, sceneState[v17].clipX, sceneState[v17].clipY, (sceneState[v17].clipX + 145), (sceneState[v17].clipY + 15))
    layerPosition(layerName.cardLabel1, 330, 5)
    v18 = (comSectionStoryGetCount()) - 2
    if (p0 < v18) and (v5 == -1) then
        v6 = 80
        v8 = 372
        v10 = 409
        v12 = 103
        v14 = 100
        v7 = 70
        v9 = 386
        v11 = 419
        v13 = 100
        v15 = 0
        v16 = p0 + 3
    elseif (3 < p0) and (v5 == 1) then
        v6 = 80
        v8 = 29
        v10 = 65
        v12 = 103
        v14 = 100
        v7 = 70
        v9 = 19
        v11 = 50
        v13 = 100
        v15 = 0
        v16 = p0 - 3
    end
    if not (v16 == 0) then
        v18 = sceneId2aCard[gameSave.storyRoute[v16].sceneId]
        layerCopy((layerName.plot - 4), plotState[v18].layerName)
        layerClip((layerName.plot - 4), plotState[v18].clipX, plotState[v18].clipY, (plotState[v18].clipX + 82), (plotState[v18].clipY + 48))
        layerCopy((layerName.plot - 3), layerName.sys_4_b)
        v0((layerName.plot - 3), gameSave.storyRoute[v16].ayanoTime)
        v19 = string.sub(gameSave.storyRoute[v16].sceneId, -4)
        if v19 == "_sel" then
            layerCopy((layerName.plot - 2), layerName.sys_2_c)
            if gameSave.myCard[v18].hold == -1 then
                if v3 == 2 then
                    layerClip((layerName.plot - 2), 0, 95, 83, 114)
                else
                    layerClip((layerName.plot - 2), 0, 76, 83, 95)
                end
            elseif v3 == 2 then
                layerClip((layerName.plot - 2), 0, 19, 83, 38)
            else
                layerClip((layerName.plot - 2), 0, 0, 83, 19)
            end
        else
            layerCopy((layerName.plot - 2), layerName.sys_2_b)
            if gameSave.myCard[v18].hold == -1 then
                if v3 == 2 then
                    layerClip((layerName.plot - 2), 0, 95, 83, 114)
                else
                    layerClip((layerName.plot - 2), 0, 76, 83, 95)
                end
            elseif v3 == 2 then
                layerClip((layerName.plot - 2), 0, 19, 83, 38)
            else
                layerClip((layerName.plot - 2), 0, 0, 83, 19)
            end
        end
        layerScale((layerName.plot - 4), v6, v6)
        layerScale((layerName.plot - 2), v6, v6)
        layerScale((layerName.plot - 3), v6, v6)
        layerMoveScale((layerName.plot - 4), v7, v7, v4)
        layerMoveScale((layerName.plot - 2), v7, v7, v4)
        layerMoveScale((layerName.plot - 3), v7, v7, v4)
        layerPosition((layerName.plot - 4), v8, 60)
        layerPosition((layerName.plot - 2), v8, v12)
        layerPosition((layerName.plot - 3), (v8 + 4), 85)
        layerMovePosition((layerName.plot - 4), v9, 60, v4)
        layerMovePosition((layerName.plot - 2), v9, v13, v4)
        layerMovePosition((layerName.plot - 3), (v9 + 4), 85, v4)
        layerAlpha((layerName.plot - 4), v14)
        layerAlpha((layerName.plot - 2), v14)
        layerAlpha((layerName.plot - 3), v14)
        layerMoveAlpha((layerName.plot - 4), v15, v4)
        layerMoveAlpha((layerName.plot - 2), v15, v4)
        i18 = layerName.plot - 3
        v23 = v15
        layerMoveAlpha(i18, v23, v4)
    end
    if 2 < p0 then
        p0 = p0 - 2
        v3 = 0
    elseif 1 < p0 then
        p0 = p0 - 1
        v3 = 1
    end
    v18 = 0
    v19 = 4
    i18 = 1
    for v23 = v18, v19, i18 do
        v21 = p0 + v23
        if gameSave.storyRoute[v21].sceneId == -1 then
            break
        end
        v22 = p0 + v23
        v20 = sceneId2aCard[gameSave.storyRoute[v22].sceneId]
        layerCopy((layerName.plot + (v23 * 4)), plotState[v20].layerName)
        layerClip((layerName.plot + (v23 * 4)), plotState[v20].clipX, plotState[v20].clipY, (plotState[v20].clipX + 82), (plotState[v20].clipY + 48))
        v22 = layerName.plot
        v24 = v23 * 4
        v22 = (v22 + v24) + 1
        layerCopy(v22, layerName.sys_4_b)
        v22 = layerName.plot
        v24 = v23 * 4
        v22 = (v22 + v24) + 1
        v0(v22, gameSave.storyRoute[(p0 + v23)].ayanoTime)
        v21 = string.sub(gameSave.storyRoute[(p0 + v23)].sceneId, -4)
        if v21 == "_sel" then
            v22 = layerName.plot
            v24 = v23 * 4
            v22 = (v22 + v24) + 2
            layerCopy(v22, layerName.sys_2_c)
            if gameSave.myCard[v20].hold == -1 then
                if v3 == 2 then
                    v22 = layerName.plot
                    v24 = v23 * 4
                    v22 = (v22 + v24) + 2
                    layerClip(v22, 0, 95, 83, 114)
                else
                    v22 = layerName.plot
                    v24 = v23 * 4
                    v22 = (v22 + v24) + 2
                    layerClip(v22, 0, 76, 83, 95)
                end
            elseif v3 == 2 then
                v22 = layerName.plot
                v24 = v23 * 4
                v22 = (v22 + v24) + 2
                layerClip(v22, 0, 19, 83, 38)
            else
                v22 = layerName.plot
                v24 = v23 * 4
                v22 = (v22 + v24) + 2
                layerClip(v22, 0, 0, 83, 19)
            end
        else
            v22 = layerName.plot
            v24 = v23 * 4
            v22 = (v22 + v24) + 2
            layerCopy(v22, layerName.sys_2_b)
            if gameSave.myCard[v20].hold == -1 then
                if v3 == 2 then
                    v22 = layerName.plot
                    v24 = v23 * 4
                    v22 = (v22 + v24) + 2
                    layerClip(v22, 0, 95, 83, 114)
                else
                    v22 = layerName.plot
                    v24 = v23 * 4
                    v22 = (v22 + v24) + 2
                    layerClip(v22, 0, 76, 83, 95)
                end
            elseif v3 == 2 then
                v22 = layerName.plot
                v24 = v23 * 4
                v22 = (v22 + v24) + 2
                layerClip(v22, 0, 19, 83, 38)
            else
                v22 = layerName.plot
                v24 = v23 * 4
                v22 = (v22 + v24) + 2
                layerClip(v22, 0, 0, 83, 19)
            end
        end
        if v3 == 0 then
            if 0 < v5 then
                v6 = 90
                v21 = (v3 + 1) * 95
                v8 = v21 + 19
                v21 = (v3 + 1) * 95
                v10 = v21 + 55
                v12 = 106
                v14 = 100
            elseif v5 < 0 then
                v6 = 70
                v21 = v3 * 95
                v8 = v21 + 19
                v21 = v3 * 95
                v10 = v21 + 50
                v12 = 100
                v14 = 0
            end
            v7 = 80
            v21 = v3 * 95
            v9 = v21 + 29
            v21 = v3 * 95
            v11 = v21 + 65
            v13 = 103
            v15 = 100
        elseif v3 == 1 then
            if 0 < v5 then
                v6 = 100
                v21 = (v3 + 1) * 95
                v8 = v21 + 9
                v21 = (v3 + 1) * 95
                v10 = v21 + 50
                v12 = 109
                v14 = 100
            elseif v5 < 0 then
                v6 = 80
                v21 = (v3 - 1) * 95
                v8 = v21 + 29
                v21 = (v3 - 1) * 95
                v10 = v21 + 65
                v12 = 103
                v14 = 100
            end
            v7 = 90
            v21 = v3 * 95
            v9 = v21 + 14
            v21 = v3 * 95
            v11 = v21 + 55
            v13 = 106
            v15 = 100
        elseif v3 == 2 then
            if 0 < v5 then
                v21 = (v3 + v5) * 95
                v8 = v21 + 4
                v21 = (v3 + v5) * 95
                v10 = v21 + 45
            elseif v5 < 0 then
                v21 = (v3 + v5) * 95
                v8 = v21 + 14
                v21 = (v3 + v5) * 95
                v10 = v21 + 55
            end
            v12 = 106
            v6 = 90
            v14 = 100
            v7 = 100
            v21 = v3 * 95
            v9 = v21 + 9
            v21 = v3 * 95
            v11 = v21 + 50
            v13 = 109
            v15 = 100
        elseif v3 == 3 then
            if 0 < v5 then
                v6 = 80
                v21 = (v3 + 1) * 95
                v8 = v21 - 8
                v21 = (v3 + 1) * 95
                v10 = v21 + 29
                v12 = 103
                v14 = 100
            elseif v5 < 0 then
                v6 = 100
                v21 = (v3 - 1) * 95
                v8 = v21 + 9
                v21 = (v3 - 1) * 95
                v10 = v21 + 50
                v12 = 109
                v14 = 100
            end
            v7 = 90
            v21 = v3 * 95
            v9 = v21 + 4
            v21 = v3 * 95
            v11 = v21 + 45
            v13 = 106
            v15 = 100
        elseif v3 == 4 then
            if 0 < v5 then
                v6 = 70
                v8 = v3 * 95
                v21 = v3 * 95
                v10 = v21 + 33
                v12 = 100
                v14 = 0
            elseif v5 < 0 then
                v6 = 90
                v21 = (v3 - 1) * 95
                v8 = v21 + 4
                v21 = (v3 - 1) * 95
                v10 = v21 + 45
                v14 = 100
                v12 = 106
            end
            v7 = 80
            v21 = v3 * 95
            v9 = v21 - 8
            v21 = v3 * 95
            v11 = v21 + 29
            v15 = 100
            v13 = 103
        end
        layerScale((layerName.plot + (v23 * 4)), v6, v6)
        v22 = layerName.plot
        v24 = v23 * 4
        v22 = (v22 + v24) + 2
        layerScale(v22, v6, v6)
        v22 = layerName.plot
        v24 = v23 * 4
        v22 = (v22 + v24) + 1
        layerScale(v22, v6, v6)
        layerMoveScale((layerName.plot + (v23 * 4)), v7, v7, v4)
        v22 = layerName.plot
        v24 = v23 * 4
        v22 = (v22 + v24) + 2
        layerMoveScale(v22, v7, v7, v4)
        v22 = layerName.plot
        v24 = v23 * 4
        v22 = (v22 + v24) + 1
        layerMoveScale(v22, v7, v7, v4)
        layerPosition((layerName.plot + (v23 * 4)), v8, 60)
        v22 = layerName.plot
        v24 = v23 * 4
        v22 = (v22 + v24) + 2
        layerPosition(v22, v8, v12)
        v22 = layerName.plot
        v24 = v23 * 4
        v22 = (v22 + v24) + 1
        layerPosition(v22, (v8 + 4), 85)
        layerMovePosition((layerName.plot + (v23 * 4)), v9, 60, v4)
        v22 = layerName.plot
        v24 = v23 * 4
        v22 = (v22 + v24) + 2
        layerMovePosition(v22, v9, v13, v4)
        v22 = layerName.plot
        v24 = v23 * 4
        v22 = (v22 + v24) + 1
        layerMovePosition(v22, (v9 + 4), 85, v4)
        layerAlpha((layerName.plot + (v23 * 4)), v14)
        v22 = layerName.plot
        v24 = v23 * 4
        v22 = (v22 + v24) + 2
        layerAlpha(v22, v14)
        v22 = layerName.plot
        v24 = v23 * 4
        v22 = (v22 + v24) + 1
        layerAlpha(v22, v14)
        layerMoveAlpha((layerName.plot + (v23 * 4)), v15, v4)
        v22 = layerName.plot
        v24 = v23 * 4
        v22 = (v22 + v24) + 2
        layerMoveAlpha(v22, v15, v4)
        v22 = layerName.plot
        v24 = v23 * 4
        v22 = (v22 + v24) + 1
        layerMoveAlpha(v22, v15, v4)
        v2 = v2 + 1
        v3 = v3 + 1
        if 5 <= v2 then
            break
        end
        if v3 == 5 then
            break
        end
    end
end
v2 = function()
    local v0, v2, v3
    savedataTitle("ストーリーモード", "")
    wait(1)
    cInitGame()
    layerCopy(100, layerName.effectBlack)
    layerCopy(layerName.bg1, layerName.bg_1_a_0)
    layerCopy((layerName.bg1 + 1), layerName.sys_2_a)
    layerClip((layerName.bg1 + 1), 0, 0, 139, 37)
    layerPosition((layerName.bg1 + 1), 5, 5)
    layerCopy((layerName.bg1 + 2), layerName.sys_2_a)
    layerClip((layerName.bg1 + 2), 0, 40, 139, 120)
    layerPosition((layerName.bg1 + 2), 195, 56)
    layerCopy((layerName.bg1 + 3), layerName.sys_2_a)
    layerClip((layerName.bg1 + 3), 0, 120, 139, 195)
    layerPosition((layerName.bg1 + 3), 338, 190)
    v1(selectItemNo, selectItemNo)
    layerLoadAsync(0, layerName.card1, cGetFileName("card", "crd_1_a"))
    layerMoveAlpha(100, 0, 60)
    wait(60)
    layerLoad(100, "")
end
main = function()
    local v0, v3, v4, v5, v6, v7, v8, v9, v10, v11, v12, v13, v14, i10, v15, v16, v17, v18, v19
    advPart(false)
    logEnable(false)
    systemConfig.unsetConfigButton()
    if gameSave.tutorial.firstFragment == 0 then
        if gameSave.startMenuState == 1 then
            doScriptScene = "s1s_10"
            run(cGetFileName("script", "snr_s1_10_s"))
            quit()
        else
            vms(16817, "NONVOICE", "【■おしらせ】ゲームメニューに、『Ｆｒａｇｍｅｎｔ』モードが追加されました。")
            vms(16818, "NONVOICE", "【■おしらせ】物語の続きはＦｒａｇｍｅｎｔモードより参照することができます。")
            cInitGame()
            run(cGetFileName("script", "snr_mainmenu"))
            quit()
        end
    end
    v0 = comSectionStoryGetCount()
    if v0 == 0 then
        doScriptScene = "s1s_20"
        run(cGetFileName("script", "snr_s1_10_s"))
        quit()
    end
    if selectItemNo < 1 then
        selectItemNo = v0
    end
    if v0 < selectItemNo then
        selectItemNo = v0
    end
    v2()
    v3 = false
    v4 = false
    v5 = 0
    v6 = selectItemNo
    v7 = v6
    v8 = false
    v9 = 1
    v10 = 1
    v11 = 1
    systemConfig.setConfigButton()
    while true do
        v12 = pressButton("RIGHT")
        if (v12 == true) and (v8 == false) and (v6 < v0) then
            v7 = v6
            v12 = v6 + 1
            if v0 < v12 then
                v6 = v0
            else
                v6 = v6 + 1
            end
            v8 = true
        end
        v12 = pressButton("LEFT")
        if (v12 == true) and (v8 == false) and (1 < v6) then
            v7 = v6
            v6 = v6 - 1
            v8 = true
        end
        v12 = pressButton("R")
        if (v12 == true) and (v8 == false) then
            v7 = v6
            v12 = v6 + 1
            v13 = v0
            v14 = 1
            for i10 = v12, v13, v14 do
                v15 = sceneId2aCard[gameSave.storyRoute[i10].sceneId]
                v6 = i10
                if gameSave.myCard[v15].hold == -1 then
                    v6 = i10
                    break
                end
            end
            wait(5)
            v8 = true
        end
        v12 = pressButton("L")
        if (v12 == true) and (v8 == false) then
            v7 = v6
            v12 = v6 - 1
            v13 = 1
            v14 = -1
            for i10 = v12, v13, v14 do
                v15 = sceneId2aCard[gameSave.storyRoute[i10].sceneId]
                v6 = i10
                if gameSave.myCard[v15].hold == -1 then
                    v6 = i10
                    break
                end
            end
            wait(5)
            v8 = true
        end
        if v8 == true then
            keyPlaySE(seName.arrowKey)
            fontClear()
            v1(v6, v7)
            v5 = 0
            v8 = false
            layerLoad(layerName.card1, "")
            layerLoad(layerName.card3, "")
            wait(3)
        end
        v12 = sceneId2aCard[gameSave.storyRoute[v6].sceneId]
        if (not (gameSave.myCard[v12].hold == -1)) and (v5 <= 3) then
            if 3 <= v5 then
                layerLoadAsync(0, layerName.card1, cGetFileName("card", "crd_" .. v12 .. "_a"))
                v4 = true
            end
            v13 = v5 + 1
            if 4 < v13 then
                v5 = 4
            else
                v5 = v5 + 1
            end
        end
        if v4 == true then
            v13 = layerIsLoad(layerName.card1)
            if v13 == true then
                layerVisible(layerName.card1, true)
                layerAlpha(layerName.card1, 0)
                layerPosition(layerName.card1, 130, 110)
                layerMovePosition(layerName.card1, 130, 130, 10)
                layerMoveAlpha(layerName.card1, 100, 10)
                v4 = false
            end
        end
        v13 = pressButton("CIRCLE")
        if not (v13 == true) then
            v9 = 0
        end
        v13 = pressButton("CIRCLE")
        if (v13 == true) and (v9 == 0) then
            if v6 == 1 then
                v13 = cGetFileName("sysgim", "sys_5_b")
                if not (v13) then
                    v13 = cGetFileName("sysgim", "sys_5_a")
                end
            else
                v13 = cGetFileName("sysgim", "sys_5_a")
            end
            fileName = v13
            keyPlaySE(seName.circle)
            v13 = comDlgYesNo(fileName, 100, 80)
            if v13 == true then
                v13 = comSectionUID2ScriptFileName(gameSave.storyRoute[v6].sceneId)
                doScriptScene = gameSave.storyRoute[v6].sceneId
                selectItemNo = -1
                gameSave.ayanoTime = gameSave.storyRoute[v6].ayanoTime
                cClearNumStoryRoute(v6)
                cInitGame()
                fontClear()
                run(cGetFileName("script", v13))
                quit()
            else
                v9 = 1
                v10 = 1
                v11 = 1
            end
            layerLoad(layerName.card3, "")
            switchScreen(0, "", 5)
            wait(5)
        end
        v13 = pressButton("CROSS")
        if not (v13 == true) then
            v10 = 0
        end
        if (pressButton("CROSS") == true) and (v10 == 0) then
            systemConfig.unsetConfigButton()
            keyPlaySE(seName.cross)
            selectItemNo = v6
            break
        else
            if not (pressButton("TRIANGLE") == true) then
                v11 = 0
            end
            if (pressButton("TRIANGLE") == true) and (v11 == 0) then
                systemConfig.unsetConfigButton()
                keyPlaySE(seName.cross)
                layerCopy(199, layerName.effectBlack)
                fontClear()
                switchScreen(0, "", 60)
                selectItemNo = v6
                comSectionFragmentItemInit()
                cInitGame()
                run(cGetFileName("script", "snr_fragment_main"))
                quit()
            end
            wait(2)
        end
    end
    layerCopy(199, layerName.effectBlack)
    fontClear()
    switchScreen(0, "", 60)
    cInitGame()
    run(cGetFileName("script", "snr_mainmenu"))
    quit()
end