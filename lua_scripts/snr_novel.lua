local v0 = {}
local v1, v2, v3, v4, v5, v6, v7, v8, v9, v10, v11, v12, v13, v14, v15, v16, v17, v18, v19, v20
v0.layerNumber = {}
v0.layerNumber.novel_1_a = 50
v0.layerNumber.novel_1_b = 51
v0.layerNumber.novel_2_a = 52
v0.layerNumber.novel_2_b = 53
v0.layerNumber.novel_2_c = 54
v0.layerNumber.novel_3_aa = 55
v0.layerNumber.novel_3_ab = 56
v0.layerNumber.novel_3_ac = 57
v0.layerNumber.novel_3_ad = 58
v0.layerNumber.novel_3_ba = 59
v0.layerNumber.novel_3_bb = 60
v0.layerNumber.novel_3_bc = 61
v0.layerNumber.novel_3_bd = 62
v0.layerNumber.novel_3_ca = 63
v0.layerNumber.novel_3_cb = 64
v0.layerNumber.novel_3_cc = 65
v0.layerNumber.novel_3_cd = 66
v0.layerNumber.novel_3_da = 67
v0.layerNumber.novel_3_db = 68
v0.layerNumber.novel_3_dc = 69
v0.layerNumber.novel_3_dd = 70
v0.layerNumber.novel_3_ea = 71
v0.layerNumber.novel_3_eb = 72
v0.layerNumber.novel_3_ec = 73
v0.layerNumber.novel_3_ed = 74
v0.layerNumber.novel_4_a = 75
v0.layerNumber.novel_4_b = 76
v0.layerNumber.novel_4_c = 77
v0.layerNumber.novel_4_d = 78
v0.indexNumber = {}
v0.indexNumber.hardCover = 0
v0.indexNumber.bar = 2
v0.indexNumber.icon = 3
v0.indexNumber.mask = 7
v0.indexNumber.key = 8
v0.indexNumber.novelBg = 0
v0.indexNumber.sentence = 1
v0.indexNumber.novelBar = 11
v0.indexNumber.title = 12
v0.indexNumber.bookMark = 13
v0.novelTitle = {}
v2 = "novel03"
v3 = "novel01"
v4 = "novel04"
v5 = "novel02"
v6 = "novel05"
v0.novelTitle[1] = v2
v0.novelTitle[2] = v3
v0.novelTitle[3] = v4
v0.novelTitle[4] = v5
v0.novelTitle[5] = v6
v0.novelKey = {}
v0.novelKey.novel01 = 1
v0.novelKey.novel02 = 2
v0.novelKey.novel03 = 3
v0.novelKey.novel04 = 4
v0.novelKey.novel05 = 5
v0.layerName = {}
v0.layerName.novel01 = "novel_3_a"
v0.layerName.novel02 = "novel_3_b"
v0.layerName.novel03 = "novel_3_c"
v0.layerName.novel04 = "novel_3_d"
v0.layerName.novel05 = "novel_3_e"
v0.novelPageMax = {}
v0.novelPageMax.novel01 = 112
v0.novelPageMax.novel02 = 159
v0.novelPageMax.novel03 = 119
v0.novelPageMax.novel04 = 119
v0.novelPageMax.novel05 = 452
v0.t_novelFlag = {}
v1 = 0
v2 = 1
v3 = 1
v4 = 5
v5 = 1
for v6 = v3, v4, v5 do
    if systemSave.novelGetFlag[v0.novelTitle[v6]] == true then
        v0.t_novelFlag[v2] = v0.novelTitle[v6]
        v2 = v2 + 1
    end
end
v3 = function(p0, p1, p2, p3)
    local v1 = 1
    local v2, v3, i4, v4, v5, v6, v7, v8
    v2 = string.len(p3)
    v3 = 1
    for i4 = v1, v2, v3 do
        v4 = string.sub(p3, i4, i4)
        v5 = (p0 + i4) - 1
        layerCopy(v5, v0.layerNumber.novel_4_c)
        v5 = (p0 + i4) - 1
        v6 = 7 * (i4 - 1)
        layerPosition(v5, p1, (p2 + v6))
        v5 = (p0 + i4) - 1
        v7 = v4 * 7
        v8 = (v4 + 1) * 7
        layerClip(v5, v7, 0, v8, 7)
    end
end
v4 = function(p0, p1, p2, p3)
    local v1, v2, v3, i4, v4, v5, v6, v7, v8
    if p3 < 10 then
        v1 = "00"
        v2 = p3
        p3 = v1 .. v2
    elseif p3 < 100 then
        v1 = "0"
        v2 = p3
        p3 = v1 .. v2
    end
    v1 = 1
    v2 = string.len(p3)
    v3 = 1
    for i4 = v1, v2, v3 do
        v4 = string.sub(p3, i4, i4)
        v5 = (p0 + i4) - 1
        layerCopy(v5, v0.layerNumber.novel_4_d)
        v5 = (p0 + i4) - 1
        v6 = 7 * (i4 - 1)
        layerPosition(v5, p1, (p2 + v6))
        v5 = (p0 + i4) - 1
        v7 = v4 * 7
        v8 = (v4 + 1) * 7
        layerClip(v5, v7, 0, v8, 7)
    end
end
v5 = function(p0)
    local v1, v2, v3, v4, v5, v6, v7
    v1 = v0.layerName[v0.t_novelFlag[p0]]
    layerCopy(v0.indexNumber.icon, v0.layerNumber[v1 .. "b"])
    layerPosition(v0.indexNumber.icon, 52, 189)
    v3 = layerCopy
    v4 = v0.indexNumber.icon + 2
    v1 = v0.layerName
    v6 = p0 - 1
    if v6 < 1 then
        v6 = #v0.t_novelFlag
    else
        v6 = p0 - 1
    end
    v1 = v1[v0.t_novelFlag[v6]]
    v3(v4, v0.layerNumber[v1 .. "b"])
    layerPosition((v0.indexNumber.icon + 2), 52, 222)
    v3 = layerCopy
    v4 = v0.indexNumber.icon + 1
    v1 = v0.layerName
    v6 = p0 + 1
    v7 = #v0.t_novelFlag
    if v7 < v6 then
        v6 = 1
    else
        v6 = p0 + 1
    end
    v1 = v1[v0.t_novelFlag[v6]]
    v3(v4, v0.layerNumber[v1 .. "b"])
    layerPosition((v0.indexNumber.icon + 1), 52, 158)
end
v6 = function(p0, p1, p2)
    local v1, v2, v3, v4, v5, v6, v7, v8
    v1 = v0.indexNumber.icon + 3
    if p2 == "down" then
        layerCopy(v1, (v0.indexNumber.icon + 1))
        layerPosition(v1, 52, 158)
        layerScale(v1, 100, 100)
        layerMoveScale(v1, 100, 0, 30)
        layerMovePosition(v1, 52, 142, 30)
        v4 = v0.layerName[v0.t_novelFlag[p0]]
        layerCopy(v0.indexNumber.icon, v0.layerNumber[v4 .. "b"])
        layerPosition(v0.indexNumber.icon, 52, 222)
        layerMovePosition(v0.indexNumber.icon, 52, 189, 30)
        v2 = v0.indexNumber.icon + 1
        v4 = v0.layerName[v0.t_novelFlag[p1]]
        layerCopy(v2, v0.layerNumber[v4 .. "b"])
        layerPosition((v0.indexNumber.icon + 1), 52, 189)
        layerMovePosition((v0.indexNumber.icon + 1), 52, 158, 30)
        v6 = layerCopy
        v2 = v0.indexNumber.icon + 2
        v4 = v0.layerName
        v7 = p0 - 1
        if v7 < 1 then
            v7 = #v0.t_novelFlag
        else
            v7 = p0 - 1
        end
        v4 = v4[v0.t_novelFlag[v7]]
        v6(v2, v0.layerNumber[v4 .. "b"])
        layerPosition((v0.indexNumber.icon + 2), 52, 235)
        layerScale((v0.indexNumber.icon + 2), 100, 0)
        layerClip((v0.indexNumber.icon + 2), 0, 0, 55, 26)
        layerMoveClip((v0.indexNumber.icon + 2), 0, 0, 55, 33, 30)
        layerMoveScale((v0.indexNumber.icon + 2), 100, 100, 30)
        layerMovePosition((v0.indexNumber.icon + 2), 52, 222, 30)
    elseif p2 == "up" then
        layerCopy(v1, (v0.indexNumber.icon + 2))
        layerPosition(v1, 52, 222)
        layerScale(v1, 100, 100)
        layerMoveClip(v1, 0, 0, 55, 26, 30)
        layerMoveScale(v1, 100, 0, 30)
        layerMovePosition(v1, 52, 235, 30)
        v4 = v0.layerName[v0.t_novelFlag[p0]]
        layerCopy(v0.indexNumber.icon, v0.layerNumber[v4 .. "b"])
        layerPosition(v0.indexNumber.icon, 52, 158)
        layerMovePosition(v0.indexNumber.icon, 52, 189, 30)
        v6 = layerCopy
        v2 = v0.indexNumber.icon + 1
        v4 = v0.layerName
        v7 = p0 + 1
        v8 = #v0.t_novelFlag
        if v8 < v7 then
            v7 = 1
        else
            v7 = p0 + 1
        end
        v4 = v4[v0.t_novelFlag[v7]]
        v6(v2, v0.layerNumber[v4 .. "b"])
        layerPosition((v0.indexNumber.icon + 1), 52, 142)
        layerScale((v0.indexNumber.icon + 1), 100, 0)
        layerMoveScale((v0.indexNumber.icon + 1), 100, 100, 30)
        layerMovePosition((v0.indexNumber.icon + 1), 52, 158, 30)
        v2 = v0.indexNumber.icon + 2
        v4 = v0.layerName[v0.t_novelFlag[p1]]
        layerCopy(v2, v0.layerNumber[v4 .. "b"])
        layerPosition((v0.indexNumber.icon + 2), 52, 189)
        layerMovePosition((v0.indexNumber.icon + 2), 52, 222, 30)
    end
end
v7 = function(p0, p1, p2)
    local v1, v2, v3
    v1 = v0.indexNumber.hardCover + 1
    v2 = v0.layerName[v0.t_novelFlag[p1]]
    layerCopy(v1, v0.layerNumber[v2 .. "a"])
    v2 = v0.layerName[v0.t_novelFlag[p0]]
    layerCopy(v0.indexNumber.hardCover, v0.layerNumber[v2 .. "a"])
    if p2 == "down" then
        layerPosition(v0.indexNumber.hardCover, 0, 270)
        layerMovePosition((v0.indexNumber.hardCover + 1), 0, -270, 30)
    elseif p2 == "up" then
        layerPosition(v0.indexNumber.hardCover, 0, -270)
        layerMovePosition((v0.indexNumber.hardCover + 1), 0, 270, 30)
    end
    layerMovePosition(v0.indexNumber.hardCover, 0, 0, 30)
    v6(p0, p1, p2)
    layerCopy(10, v0.layerNumber.novel_4_b)
    layerClip(10, 0, 0, 7, 61)
    layerPosition(10, 115, 205)
    if not (systemSave.bookMark[v0.t_novelFlag[p0]] == 0) then
        v4(11, 115, 250, systemSave.bookMark[v0.t_novelFlag[p0]])
    else
        layerLoad(11, "")
        layerLoad(12, "")
        layerLoad(13, "")
        layerClip(10, 7, 0, 14, 61)
    end
    wait(30)
    layerLoad((v0.indexNumber.hardCover + 1), "")
end
v8 = function(p0)
    local v1, v2, v6
    v1 = v0.layerName[v0.t_novelFlag[p0]]
    layerCopy(v0.indexNumber.hardCover, v0.layerNumber[v1 .. "a"])
    v5(p0)
    layerCopy(v0.indexNumber.bar, v0.layerNumber.novel_1_a)
    layerPosition(v0.indexNumber.bar, 15, 0)
    layerCopy(v0.indexNumber.mask, v0.layerNumber.novel_1_b)
    layerPosition(v0.indexNumber.mask, 59, 158)
    v2 = "0"
    v6 = #v0.t_novelFlag
    v3(14, 91, 10, v2 .. v6)
    v3(16, 91, 40, "05")
    layerCopy(10, v0.layerNumber.novel_4_b)
    layerClip(10, 0, 0, 7, 61)
    layerPosition(10, 115, 205)
    if not (systemSave.bookMark[v0.t_novelFlag[p0]] == 0) then
        v4(11, 115, 250, systemSave.bookMark[v0.t_novelFlag[p0]])
    else
        layerClip(10, 7, 0, 14, 61)
    end
    switchScreen(0, "", 60)
end
v9 = function()
    local v0 = 0
    local v1 = 20
    local v2 = 1
    local i0
    for i0 = v0, v1, v2 do
        layerLoad(i0, "")
    end
    switchScreen(0, "", 60)
end
v10 = function(p0)
    local v2, v3, v4, v5, v6, v10
    if p0 then
        v2 = p0
    else
        v2 = 1
    end
    v8(v2)
    v3 = 1
    v4 = false
    v5 = ""
    while true do
        v6 = pressButton("UP")
        if (v6 == true) and (v4 == false) then
            v3 = v2
            v6 = v2 + 1
            v10 = #v0.t_novelFlag
            if v10 < v6 then
                v2 = 1
            else
                v2 = v2 + 1
            end
            v4 = true
            v5 = "up"
        end
        v6 = pressButton("DOWN")
        if (v6 == true) and (v4 == false) then
            v3 = v2
            v6 = v2 - 1
            if v6 < 1 then
                v6 = #v0.t_novelFlag
                if not (v6) then
                    v2 = v2 - 1
                else
                    v2 = v6
                end
            else
                v2 = v2 - 1
            end
            v4 = true
            v5 = "down"
        end
        v6 = pressButton("RIGHT")
        if (v6 == true) and (v4 == false) then
            v1 = 2
            keyPlaySE(seName.cross)
            break
        else
            v6 = pressButton("LEFT")
            if (v6 == true) and (v4 == false) then
                keyPlaySE(seName.circle)
                v1 = 1
                break
            else
                if v4 == true then
                    keyPlaySE(seName.arrowKey)
                    v7(v2, v3, v5)
                    v4 = false
                end
                wait(2)
            end
        end
    end
    v9()
    return v2
end
v11 = function(p0, p1, p2)
    local v1, v2, v3, v4, v5, v6
    if p2 == 1 then
        comLayerLoadFalse((v0.indexNumber.sentence + 4), "novel/" .. v0.t_novelFlag[p0] .. "_" .. (p1 - 2) .. ".gim")
        comLayerLoadFalse((v0.indexNumber.sentence + 5), "novel/" .. v0.t_novelFlag[p0] .. "_" .. (p1 + 2) .. ".gim")
    elseif p2 == 2 then
        comLayerLoadFalse(v0.indexNumber.sentence, "novel/" .. v0.t_novelFlag[p0] .. "_" .. (p1 - 2) .. ".gim")
        comLayerLoadFalse((v0.indexNumber.sentence + 1), "novel/" .. v0.t_novelFlag[p0] .. "_" .. (p1 + 2) .. ".gim")
    elseif p2 == 3 then
        comLayerLoadFalse((v0.indexNumber.sentence + 2), "novel/" .. v0.t_novelFlag[p0] .. "_" .. (p1 - 2) .. ".gim")
        comLayerLoadFalse((v0.indexNumber.sentence + 3), "novel/" .. v0.t_novelFlag[p0] .. "_" .. (p1 + 2) .. ".gim")
    end
end
v12 = function(p0, p1, p2)
    local v1, v2, v5, v6, v7, v8
    v1 = v0.layerName[v0.t_novelFlag[p0]]
    layerCopy(v0.indexNumber.novelBg, v0.layerNumber[v1 .. "d"])
    layerCopy(v0.indexNumber.novelBar, v0.layerNumber.novel_4_a)
    v1 = v0.layerName[v0.t_novelFlag[p0]]
    layerCopy(v0.indexNumber.title, v0.layerNumber[v1 .. "c"])
    layerPosition(v0.indexNumber.title, 462, 5)
    layerCopy(v0.indexNumber.bookMark, v0.layerNumber.novel_4_b)
    if systemSave.bookMark[v0.novelTitle[p0]] == 0 then
        layerClip(v0.indexNumber.bookMark, 7, 0, 14, 61)
    else
        layerClip(v0.indexNumber.bookMark, 0, 0, 7, 61)
        v4(28, 457, 245, systemSave.bookMark[v0.t_novelFlag[p0]])
    end
    layerPosition(v0.indexNumber.bookMark, 457, 200)
    if p1 < 10 then
        v3(14, 470, 205, "00" .. p1)
    elseif p1 < 100 then
        v3(14, 470, 205, "0" .. p1)
    else
        v3(14, 470, 205, p1)
    end
    v3(17, 470, 243, v0.novelPageMax[v0.t_novelFlag[p0]])
    layerLoad(v0.indexNumber.sentence, "novel/" .. v0.t_novelFlag[p0] .. "_" .. p1 .. ".gim")
    comLayerLoadFalse((v0.indexNumber.sentence + 2), "novel/" .. v0.t_novelFlag[p0] .. "_" .. (p1 - 1) .. ".gim")
    comLayerLoadFalse((v0.indexNumber.sentence + 3), "novel/" .. v0.t_novelFlag[p0] .. "_" .. (p1 + 1) .. ".gim")
    layerPosition(v0.indexNumber.sentence, 20, 0)
    v11(p0, p1, p2)
    switchScreen(0, "", 60)
end
v13 = function()
    local v0 = 0
    local v1 = 40
    local v2 = 1
    local i0
    for i0 = v0, v1, v2 do
        layerLoad(i0, "")
    end
    fontClear()
    switchScreen(0, "", 60)
end
v14 = function(p0, p1)
    if systemSave.bookMark[v0.t_novelFlag[p0]] == p1 then
        layerLoad(28, "")
        layerLoad(29, "")
        layerLoad(30, "")
        systemSave.bookMark[v0.t_novelFlag[p0]] = 0
        layerClip(v0.indexNumber.bookMark, 7, 0, 14, 61)
    else
        systemSave.bookMark[v0.t_novelFlag[p0]] = p1
        layerClip(v0.indexNumber.bookMark, 0, 0, 7, 61)
        v4(28, 457, 245, systemSave.bookMark[v0.t_novelFlag[p0]])
    end
end
v15 = function(p0)
    local v2, v4, v5, v6, v7, v8, v9, v10, v15, v16, v17, v18, v19, v20
    if 0 < systemSave.bookMark[v0.t_novelFlag[p0]] then
        v2 = systemSave.bookMark[v0.t_novelFlag[p0]]
        if not (v2) then
            v2 = 1
        end
    else
        v2 = 1
    end
    v4 = 1
    v5 = false
    v6 = 1
    v7 = 1
    v8 = 1
    v9 = 1
    v12(p0, v2, v9)
    while true do
        v10 = pressButton("UP")
        if (v10 == true) and (v5 == false) then
            v4 = v2
            v10 = v2 + 1
            if v0.novelPageMax[v0.t_novelFlag[p0]] < v10 then
                if not (v0.novelPageMax[v0.t_novelFlag[p0]]) then
                    v2 = v2 + 1
                else
                    v2 = v0.novelPageMax[v0.t_novelFlag[p0]]
                end
            else
                v2 = v2 + 1
            end
            v5 = true
        end
        v10 = pressButton("DOWN")
        if (v10 == true) and (v5 == false) then
            v4 = v2
            v10 = v2 - 1
            if v10 < 1 then
                v2 = 1
            else
                v2 = v2 - 1
            end
            v5 = true
        end
        v10 = pressButton("RIGHT")
        if (v10 == true) and (v5 == false) then
            keyPlaySE(seName.cross)
            v1 = 0
            break
        else
            v10 = pressButton("LEFT")
            if (v10 == true) and (v5 == false) then
                v14(p0, v2)
                wait(10)
            end
            if v5 == true then
                fontClear()
                if not (v2 == v4) then
                    v8 = v7
                    v10 = v2 - v4
                    if 0 < v10 then
                        v7 = 1
                        if v9 == 1 then
                            v6 = 3
                            v9 = 2
                        elseif v9 == 2 then
                            v6 = 5
                            v9 = 3
                        elseif v9 == 3 then
                            v6 = 1
                            v9 = 1
                        end
                    else
                        v7 = -1
                        if v9 == 1 then
                            v6 = 2
                            v9 = 2
                        elseif v9 == 2 then
                            v6 = 4
                            v9 = 3
                        elseif v9 == 3 then
                            v6 = 0
                            v9 = 1
                        end
                    end
                    wait(5)
                    if not (v7 == v8) then
                        v9 = 1
                        v6 = 0
                        layerLoad((v0.indexNumber.sentence + 1), "")
                        layerLoad((v0.indexNumber.sentence + 2), "")
                        layerLoad((v0.indexNumber.sentence + 3), "")
                        layerLoad((v0.indexNumber.sentence + 4), "")
                        layerLoad((v0.indexNumber.sentence + 5), "")
                        layerLoad(v0.indexNumber.sentence, "novel/" .. v0.t_novelFlag[p0] .. "_" .. v2 .. ".gim")
                        layerPosition((v0.indexNumber.sentence + v6), 20, 0)
                        comLayerLoadFalse((v0.indexNumber.sentence + 2), "novel/" .. v0.t_novelFlag[p0] .. "_" .. (v2 - 1) .. ".gim")
                        comLayerLoadFalse((v0.indexNumber.sentence + 3), "novel/" .. v0.t_novelFlag[p0] .. "_" .. (v2 + 1) .. ".gim")
                        v11(p0, v2, v9)
                    else
                        while true do
                            v10 = layerIsLoad((v0.indexNumber.sentence + v6))
                            if v10 == true then
                                layerVisible((v0.indexNumber.sentence + v6), true)
                                layerPosition((v0.indexNumber.sentence + v6), 20, 0)
                                v11(p0, v2, v9)
                                break
                            else
                                wait(1)
                            end
                        end
                    end
                end
                if v2 < 10 then
                    v3(14, 470, 205, "00" .. v2)
                elseif v2 < 100 then
                    v3(14, 470, 205, "0" .. v2)
                else
                    v3(14, 470, 205, v2)
                end
                v5 = false
            end
            wait(2)
        end
    end
    v13()
end
main = function()
    local v3, v4, v5, g3, g4, v6, v7, v8
    if v2 == 1 then
        msg("まだ一冊も取得していません。") -- tr_line:557
        run(cGetFileName("script", "snr_mainmenu"))
    end
    systemConfig.unsetConfigButton()
    logEnable(false)
    advPart(false)
    startLoading()
    v4 = v0.layerNumber
    v3, v4, v5 = pairs(v4)
    for g3, g4 in v3, v4, v5 do
        comLayerLoadFalse(g4, "novel/" .. g3 .. ".gim")
    end
    waitLoading()
    endLoading()
    v3 = 1
    while v1 < 2 do
        if v1 == 0 then
            v3 = v10(v3)
        elseif v1 == 1 then
            v15(v3)
        end
        wait(2)
    end
    autoSystemSave(0)
    cInitGame()
    run(cGetFileName("script", "snr_mainmenu"))
end