-- Style engine. Each change creates a new composition; the previous one survives.
local M = {}
M.labels = {"Standard Text+", "Sanftes Ein-/Ausblenden", "Ghostly Mist Dissolve"}
local function need(value, message)
    assert(value ~= nil and value ~= false, message)
    return value
end
function M.source(clip)
    local names = clip:GetFusionCompNameList() or {}
    for i=#names,1,-1 do
        local comp = clip:GetFusionCompByName(names[i])
        local text = comp and (comp:FindTool("GhostlyMistDissolve") or comp:FindTool("Lyrics_Text"))
        if text then return comp, text, names[i], i end
    end
end
function M.apply(clip, style, root)
    assert(style == 1 or style == 2 or style == 3, "Unbekannter Stil.")
    local original, source, originalName, originalIndex = M.source(clip)
    assert(original, "Kein Lyrics-Studio-Titel: " .. clip:GetName())
    local start, finish = clip:GetStart(), clip:GetEnd()
    local values = {}
    for _,key in ipairs({"StyledText","Font","Style","Size","Center","Red1","Green1","Blue1","Alpha1"}) do
        values[key] = source:GetInput(key)
    end
    assert(type(values.StyledText) == "string", "Titeltext fehlt.")
    local id = tostring(os.time()) .. "_" .. tostring(math.random(100000,999999))
    local file = root .. "/comps/Style_" .. id .. ".comp"
    need(clip:ExportFusionComp(file, originalIndex), "Komposition konnte nicht gesichert werden.")
    local comp, workingName, finalName
    local ok, problem = xpcall(function()
        -- Resolve 21 imports into the active composition despite the API stub
        -- describing ImportFusionComp as adding one. Allocate it explicitly.
        need(clip:AddFusionComp(), "Arbeitskopie konnte nicht angelegt werden.")
        local names = clip:GetFusionCompNameList()
        local candidate = names[#names]
        assert(candidate ~= originalName, "Keine unabhängige Arbeitskopie angelegt.")
        workingName = candidate
        comp = need(clip:ImportFusionComp(file), "Arbeitskopie konnte nicht geladen werden.")
        need(clip:LoadFusionCompByName(workingName), "Arbeitskopie konnte nicht aktiviert werden.")
        comp:Lock()
        for _,name in ipairs({"GhostlyMistDissolve","Lyrics_StyleFade","Lyrics_StyleTransparent"}) do
            local tool = comp:FindTool(name)
            if tool then tool:Delete() end
        end
        local text = comp:FindTool("Lyrics_Text") or need(comp:AddTool("TextPlus"), "Text+ fehlt.")
        text:SetAttrs({TOOLS_Name="Lyrics_Text"})
        local target = text
        if style == 3 then
            local graph = need(bmd.readfile(root .. "/Ghostly Mist Dissolve.setting"), "Ghostly-Mist-Vorlage fehlt.")
            comp:Unlock()
            assert(comp:Paste(graph) ~= false, "Ghostly Mist konnte nicht geladen werden.")
            comp:Lock()
            target = need(comp:FindTool("GhostlyMistDissolve"), "Ghostly-Mist-Knoten fehlt.")
        end
        for key,value in pairs(values) do
            assert(target:SetInput(key,value) ~= false, "Stileinstellung fehlt: " .. key)
        end
        if style == 2 then
            local background = need(comp:AddTool("Background"), "Transparenter Hintergrund fehlt.")
            background:SetAttrs({TOOLS_Name="Lyrics_StyleTransparent"})
            background:SetInput("TopLeftAlpha",0)
            local fade = need(comp:AddTool("Dissolve"), "Überblendung fehlt.")
            fade:SetAttrs({TOOLS_Name="Lyrics_StyleFade"})
            need(fade:ConnectInput("Background",background), "Hintergrund fehlt.")
            need(fade:ConnectInput("Foreground",text), "Text fehlt.")
            -- 20% at each end, capped at a quarter second at the composition FPS.
            local frames = math.max(1, math.min((finish-start-1)*0.2, (comp:GetPrefs("Comp.FrameFormat.Rate") or 24)*0.25))
            fade.Mix:SetExpression(string.format("min(1,max(0,(time-comp.RenderStart)/%.8f),max(0,(comp.RenderEnd-time)/%.8f))", frames, frames))
            target = fade
        end
        local output = need(comp:FindTool("MediaOut1"), "Medienausgabe fehlt.")
        need(output:ConnectInput("Input",target), "Stilausgabe fehlt.")
        comp:Unlock()
        need(clip:ExportFusionComp(file, #clip:GetFusionCompNameList()), "Stil konnte nicht gesichert werden.")
        local persisted = need(clip:ImportFusionComp(file), "Stil konnte nicht aktiviert werden.")
        local names = clip:GetFusionCompNameList()
        finalName = names[#names]
        need(clip:LoadFusionCompByName(finalName), "Stil konnte nicht geladen werden.")
        local check = style == 3 and persisted:FindTool("GhostlyMistDissolve") or persisted:FindTool("Lyrics_Text")
        assert(check and check:GetInput("StyledText") == values.StyledText, "Textkontrolle fehlgeschlagen.")
        assert(clip:GetStart() == start and clip:GetEnd() == finish, "Clipzeiten wurden verändert.")
    end, debug.traceback)
    if not ok then
        if comp then pcall(function() comp:Unlock() end) end
        clip:LoadFusionCompByName(originalName)
        if finalName and finalName ~= workingName then clip:DeleteFusionCompByName(finalName) end
        if workingName then clip:DeleteFusionCompByName(workingName) end
        error(problem)
    end
    return originalName, finalName, workingName
end
return M
