-- Optional Hammerspoon bridge: require this module and call .start().
-- No accessibility calls or subprocesses; writes only wake/unlock timestamps.
local M = {}
local directory = os.getenv('HOME') .. '/.local/state/terminal-setup'
local function record(name)
    local path = directory .. '/last-' .. name
    local f = io.open(path .. '.tmp', 'w')
    if f then f:write(tostring(os.time()), '\n'); f:close(); os.rename(path .. '.tmp', path) end
end
function M.start()
    if M.watcher then M.watcher:stop() end
    hs.fs.mkdir(directory)
    M.watcher = hs.caffeinate.watcher.new(function(event)
        if event == hs.caffeinate.watcher.systemDidWake then record('wake') end
        if event == hs.caffeinate.watcher.screensDidUnlock then record('unlock') end
    end):start()
    return M
end
return M
