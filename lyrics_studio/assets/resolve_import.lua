-- Lyrics Studio: creates only a new timeline and a new media bin.
-- Run with dofile("/path/to/Import_in_DaVinci.lua") in Resolve's Lua console.
local script = debug.getinfo(1, "S").source
assert(script:sub(1,1) == "@", "Bitte dieses Script mit dofile laden.")
local root = assert(script:sub(2):match("^(.*)[/\\]"), "Paketordner nicht gefunden.")
local data = dofile(root .. "/Titel_Daten.lua")
local app = assert(bmd.scriptapp("Resolve"), "DaVinci Resolve ist nicht bereit.")
local project = assert(app:GetProjectManager():GetCurrentProject(), "Bitte ein Resolve-Projekt öffnen.")
local pool = project:GetMediaPool()
local previous = project:GetCurrentTimeline()
local previousFolder = pool:GetCurrentFolder()
local timeline = nil
local lockedComp = nil
local function require_ok(value, message)
    assert(value ~= false and value ~= nil, message)
    return value
end
for index=1,project:GetTimelineCount() do
    local existing = project:GetTimelineByIndex(index):GetName()
    assert(existing ~= data.name and existing ~= data.name .. " [UNVOLLSTAENDIG]",
        "Dieses Paket wurde bereits oder unvollständig importiert. Bitte eine neue Exportausgabe verwenden. Keine Änderungen vorgenommen.")
end
local function setting(object, key, value)
    -- SetSetting is also supported by older Resolve releases.
    return object:SetSetting(key, tostring(value))
end
local ok, problem = xpcall(function()
    print("Lyrics Studio: Import startet (" .. #data.rows .. " Passagen).")
    timeline = require_ok(pool:CreateEmptyTimeline(data.name), "Neue Timeline konnte nicht angelegt werden.")
    require_ok(project:SetCurrentTimeline(timeline), "Neue Timeline konnte nicht aktiviert werden.")
    setting(timeline, "useCustomSettings", 1)
    setting(timeline, "timelineFrameRate", data.fps)
    setting(timeline, "timelineResolutionWidth", data.width)
    setting(timeline, "timelineResolutionHeight", data.height)
    assert(tonumber(timeline:GetSetting("timelineFrameRate")) == data.fps, "Bildrate konnte nicht gesetzt werden. Bitte Exportbildrate und Projektbildrate angleichen.")
    assert(tonumber(timeline:GetSetting("timelineResolutionWidth")) == data.width and tonumber(timeline:GetSetting("timelineResolutionHeight")) == data.height, "Timeline-Auflösung stimmt nicht mit dem Export überein.")
    require_ok(timeline:SetStartTimecode("00:00:00:00"), "Timeline-Start konnte nicht gesetzt werden.")
    assert(timeline:GetStartFrame() == 0, "Timeline beginnt nicht bei Frame 0.")
    local folder = require_ok(pool:AddSubFolder(pool:GetRootFolder(), data.name), "Medienordner konnte nicht angelegt werden.")
    require_ok(pool:SetCurrentFolder(folder), "Medienordner konnte nicht ausgewählt werden.")
    local media = pool:ImportMedia({{FilePath=root .. "/carrier/Carrier_%06d.png", StartIndex=0, EndIndex=data.carrier_frames-1}})
    assert(media and #media == 1, "Transparente Titelmedien konnten nicht importiert werden.")
    local carrier = media[1]
    if tonumber(carrier:GetClipProperty("FPS")) ~= data.fps then
        require_ok(carrier:SetClipProperty("FPS", tostring(data.fps)), "Bildrate der Titelmedien konnte nicht angepasst werden.")
    end
    assert(tonumber(carrier:GetClipProperty("FPS")) == data.fps, "Titelmedien haben eine andere Bildrate.")
    while timeline:GetTrackCount("video") < data.tracks do require_ok(timeline:AddTrack("video"), "Videospur fehlt.") end
    for track=1,data.tracks do timeline:SetTrackName("video", track, "Lyrics " .. track) end
    if data.audio then
        local audio = pool:ImportMedia({root .. "/" .. data.audio})
        assert(audio and #audio == 1, "Song konnte nicht importiert werden.")
        if timeline:GetTrackCount("audio") == 0 then require_ok(timeline:AddTrack("audio", "stereo"), "Audiospur fehlt.") end
        local clips = pool:AppendToTimeline({{mediaPoolItem=audio[1], recordFrame=data.audio_start_frame, trackIndex=1, mediaType=2}})
        assert(clips and #clips == 1 and clips[1]:GetStart() == data.audio_start_frame, "Song konnte nicht zeitgerecht platziert werden.")
    end
    for index,row in ipairs(data.rows) do
        local duration = row.end_frame-row.start_frame
        local function append(sourceEnd)
            local clips = pool:AppendToTimeline({{mediaPoolItem=carrier, startFrame=0, endFrame=sourceEnd,
                recordFrame=row.start_frame, trackIndex=row.track, mediaType=1}})
            assert(clips and #clips == 1, "Titel konnte nicht angelegt werden: " .. row.id)
            return clips[1]
        end
        local clip = append(duration)
        -- Resolve versions differ on whether source endFrame is inclusive.
        if clip:GetStart() == row.start_frame and clip:GetEnd() == row.end_frame+1 then
            require_ok(timeline:DeleteClips({clip}, false), "Korrektur des neu erzeugten Clips fehlgeschlagen.")
            clip = append(duration-1)
        end
        assert(clip:GetStart() == row.start_frame and clip:GetEnd() == row.end_frame, "Titelzeit stimmt nicht überein: " .. row.id)
        require_ok(clip:SetName(row.id), "Titelname konnte nicht gesetzt werden.")
        local comp = require_ok(clip:AddFusionComp(), "Fusion-Komposition konnte nicht erzeugt werden.")
        comp:Lock()
        lockedComp = comp
        local text = require_ok(comp:AddTool("TextPlus"), "Text+ ist nicht verfügbar.")
        text:SetAttrs({TOOLS_Name="Lyrics_Text"})
        local inputs = {StyledText=row.text, Font="Arial", Style="Regular", Size=0.045,
            HorizontalJustificationNew=3, VerticalJustificationNew=3, Red1=1, Green1=1, Blue1=1, Alpha1=1}
        for key,value in pairs(inputs) do
            assert(text:SetInput(key,value) ~= false, "Text+-Einstellung fehlt: " .. key)
            local actual = text:GetInput(key)
            assert(actual == value or type(actual) == "number" and type(value) == "number" and math.abs(actual-value) < 0.000001,
                "Text+-Einstellung stimmt nicht: " .. key)
        end
        local step = math.min(0.10, 0.65/math.max(1,data.tracks-1))
        assert(text:SetInput("Center", {0.5, 0.18+(row.track-1)*step}) ~= false, "Textposition konnte nicht gesetzt werden.")
        require_ok(comp:FindTool("MediaOut1"):ConnectInput("Input",text), "Text+-Ausgabe fehlt.")
        comp:Unlock()
        lockedComp = nil
        assert(text:GetInput("StyledText") == row.text, "Text stimmt nicht mit dem Export überein.")
        local file = root .. "/comps/Title_" .. string.format("%04d",index) .. ".comp"
        require_ok(clip:ExportFusionComp(file,1), "Native Komposition konnte nicht gesichert werden.")
        require_ok(clip:ImportFusionComp(file), "Native Komposition konnte nicht aktiviert werden.")
        local names = clip:GetFusionCompNameList()
        require_ok(clip:LoadFusionCompByName(names[#names]), "Text+-Komposition konnte nicht geladen werden.")
        local active = clip:GetFusionCompByIndex(#names)
        assert(active and active:FindTool("Lyrics_Text"):GetInput("StyledText") == row.text, "Text+-Kontrolle fehlgeschlagen.")
        if index % 10 == 0 then print("Lyrics Studio: " .. index .. "/" .. #data.rows .. " Titel importiert.") end
    end
end, debug.traceback)
if previousFolder then pool:SetCurrentFolder(previousFolder) end
if not ok then
    if lockedComp then pcall(function() lockedComp:Unlock() end) end
    if timeline then timeline:SetName(data.name .. " [UNVOLLSTAENDIG]") end
    if previous then project:SetCurrentTimeline(previous) end
    local report = io.open(root .. "/IMPORT-FEHLER.txt", "w")
    if report then report:write(tostring(problem)); report:close() end
    error("Lyrics-Import angehalten. Eine neue unvollständige Timeline bleibt zur Prüfung erhalten.\n" .. tostring(problem))
end
print("Lyrics Studio: " .. #data.rows .. " bearbeitbare Text+-Clips importiert. Timeline: " .. data.name)
print("Bitte das Resolve-Projekt speichern und den gesamten Exportordner behalten.")
local receipt = io.open(root .. "/IMPORT-ERGEBNIS.txt", "w")
if receipt then
    receipt:write("OK\n" .. timeline:GetUniqueId() .. "\n" .. #data.rows .. "\n")
    receipt:close()
end
