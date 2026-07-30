local v0
main = function()
    local v0
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    vms(282, "NONVOICE", "≪入手済みカード≫")
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end