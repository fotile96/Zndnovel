local v0, v1, v2, v3, v4, v5
libGomRin = function()
end
main = function()
    local v0, v1, v2, v3, v4, v5, i3
    cInitGame()
    v0 = 1
    v1 = false
    cfontPrint(0, 200, 100, 16777215, 255, "SEC7F")
    cfontPrint(0, 200, 150, 16777215, 16711680, "PROLOGUE")
    cfontPrint(0, 200, 200, 16777215, 16711680, "STORY")
    cfontPrint(0, 200, 250, 16777215, 16711680, "DEBUG")
    v2 = 1
    while true do
        v3 = pressButton("UP")
        if (v3 == true) and (v1 == false) then
            v3 = v0 - 1
            if v3 < 1 then
                v0 = 1
            else
                v0 = v0 - 1
            end
            v1 = true
        end
        v3 = pressButton("DOWN")
        if (v3 == true) and (v1 == false) then
            v3 = v0 + 1
            if 4 < v3 then
                v0 = 4
            else
                v0 = v0 + 1
            end
            v1 = true
        end
        v3 = pressButton("CIRCLE")
        if v3 == true then
            if v2 == 0 then
                break
            end
        else
            v2 = 0
        end
        if v1 == true then
            fontClear()
            if v0 == 1 then
                cfontPrint(0, 200, 100, 16777215, 255, "SEC7F")
            else
                cfontPrint(0, 200, 100, 16777215, 16711680, "SEC7F")
            end
            if v0 == 2 then
                cfontPrint(0, 200, 150, 16777215, 255, "PROLOGUE")
            else
                cfontPrint(0, 200, 150, 16777215, 16711680, "PROLOGUE")
            end
            if v0 == 3 then
                cfontPrint(0, 200, 200, 16777215, 255, "STORY")
            else
                cfontPrint(0, 200, 200, 16777215, 16711680, "STORY")
            end
            if v0 == 4 then
                cfontPrint(0, 200, 250, 16777215, 255, "DEBUG")
            else
                cfontPrint(0, 200, 250, 16777215, 16711680, "DEBUG")
            end
            v1 = false
            wait(5)
        end
        wait(1)
    end
    fontClear()
    if v0 == 1 then
        cardIDFlag = true
        v3 = 1
        v4 = 195
        v5 = 1
        for i3 = v3, v4, v5 do
            gameSave.myCard[i3].hold = 1
        end
        gameSave.startMenuState = 2
        gameSave.myCard[1].hold = 1
        gameSave.myCard[2].hold = 1
        gameSave.tutorial.firstStory = 1
        gameSave.tutorial.firstFragmentBegin = 1
        gameSave.tutorial.firstFragment = 1
        gameSave.ayanoTime = 0
        gameSave.storyRoute[1].sceneId = "e1s_10"
        gameSave.storyRoute[1].ayanoTime = 0
        run(cGetFileName("script", "snr_fragment_main"))
        quit()
    end
    run(cGetFileName("script", "snr_mainmenu"))
    quit()
end