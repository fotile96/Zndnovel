local v0
main = function()
    local v0
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    vms(630, "NONVOICE", "≪この場面は、直哉と彩野によるカード選択シーンはありません≫")
    comSectionCardEnd(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    run(cGetFileName("script", "snr_fragment_main"))
    quit()
end