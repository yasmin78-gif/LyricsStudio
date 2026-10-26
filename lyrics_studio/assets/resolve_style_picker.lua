-- Run from Resolve's Lua console after selecting timeline clips.
local path = debug.getinfo(1,"S").source
assert(path:sub(1,1) == "@", "Bitte dieses Script mit dofile laden.")
local root = assert(path:sub(2):match("^(.*)[/\\]"))
local styles = dofile(root .. "/Lyrics_Stile.lua")
local resolve = assert(bmd.scriptapp("Resolve"), "Resolve ist nicht bereit.")
local project = assert(resolve:GetProjectManager():GetCurrentProject(), "Bitte ein Projekt öffnen.")
local timeline = assert(project:GetCurrentTimeline(), "Bitte eine Timeline öffnen.")
local ok, selected = pcall(function() return timeline:GetSelectedClips() end)
assert(ok and selected, "Diese Resolve-Version unterstützt die Clipauswahl per Script nicht. Benötigt wird eine Version mit Timeline:GetSelectedClips().")
local clips, skipped = {}, 0
for _,clip in ipairs(selected) do
    if styles.source(clip) then clips[#clips+1] = clip else skipped = skipped+1 end
end
assert(#clips > 0, "Bitte zuerst Lyrics-Studio-Clips in der Edit-Timeline markieren.")
local dialogComp = styles.source(clips[1])
local answer = dialogComp:AskUser("Lyrics Studio · Titelstil", {
    {"Info", "Text", Name="Auswahl", Default=tostring(#clips) .. " Lyrics-Clips; " .. skipped .. " andere Clips werden übersprungen. Vorherige Kompositionen bleiben erhalten.", ReadOnly=true, Lines=3},
    {"Style", "Dropdown", Name="Animation", Options=styles.labels, Default=0}
})
if not answer then return end
-- Verify context and selection again after the modal dialog.
assert(project:GetCurrentTimeline():GetUniqueId() == timeline:GetUniqueId(), "Die Timeline wurde gewechselt. Bitte erneut starten.")
local changed = {}
local previousPage = resolve:GetCurrentPage()
local success, problem = xpcall(function()
    assert(resolve:OpenPage("fusion"), "Fusion-Seite konnte nicht geöffnet werden.")
    for _,clip in ipairs(clips) do
        local original, final = styles.apply(clip, answer.Style+1, root)
        changed[#changed+1] = {clip=clip, original=original, final=final}
    end
end, debug.traceback)
if previousPage then resolve:OpenPage(previousPage) end
if not success then
    for i=#changed,1,-1 do
        local entry = changed[i]
        entry.clip:LoadFusionCompByName(entry.original)
        entry.clip:DeleteFusionCompByName(entry.final)
    end
    error("Stilwechsel abgebrochen; vorherige Kompositionen wieder aktiviert.\n" .. tostring(problem))
end
print("Lyrics Studio: " .. #changed .. " Titel mit „" .. styles.labels[answer.Style+1] .. "“. Text und Clipzeiten beibehalten. Bitte Resolve-Projekt speichern.")
