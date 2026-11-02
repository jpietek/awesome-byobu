-- Terminal-only controls. No physical modifier remapping or GUI-app shortcuts.
local M = {releases={}}
local iterm = 'com.googlecode.iterm2'
local types = hs.eventtap.event.types
local props = hs.eventtap.event.properties
local sequence, mouseLink, middleDown
local function now() return hs.timer.absoluteTime() / 1e9 end

-- WindowServer metadata avoids slow synchronous AX focus lookups on every key.
function M.context(event, mouse)
    local wanted
    if mouse and event then
        wanted = event:getProperty(props.mouseEventWindowUnderMousePointerThatCanHandleThisEvent)
        if not wanted or wanted == 0 then wanted = event:getProperty(props.mouseEventWindowUnderMousePointer) end
    end
    for _, window in ipairs(hs.window.list() or {}) do
        local bounds = window.kCGWindowBounds or {}
        if window.kCGWindowIsOnscreen and (window.kCGWindowAlpha or 0) > 0 and
           (bounds.Width or 0) > 40 and (bounds.Height or 0) > 40 and
           (not wanted or wanted == 0 or wanted == window.kCGWindowNumber) then
            local app = hs.application.applicationForPID(window.kCGWindowOwnerPID)
            if app and app:bundleID() == iterm then
                return {id=window.kCGWindowNumber, pid=window.kCGWindowOwnerPID}
            end
            return nil
        end
    end
end

function M.sameTarget(target)
    local current = M.context()
    return target and current and target.id == current.id and target.pid == current.pid
end

function M.menu(action, target)
    if not M.sameTarget(target) then return end
    local app = hs.application.applicationForPID(target.pid)
    if not app:selectMenuItem({'Edit', action}) then
        -- Native Cmd-C/V keeps iTerm's bracketed-paste and confirmation behavior.
        hs.eventtap.keyStroke({'cmd'}, action == 'Copy' and 'c' or 'v', 0, app)
    end
end

local function deferredMenu(action, target)
    hs.timer.doAfter(0, function() M.menu(action, target) end)
end

-- Short, stationary three-finger tap/click. A swipe or fourth finger cancels it.
function M.feed(touches, time)
    if sequence and time - sequence.start > 1.5 then sequence = nil end
    local active, total = 0, 0
    for _, touch in ipairs(touches) do
        if touch.type == 'indirect' and not touch.resting then
            total = total + 1
            if touch.touching then active = active + 1 end
        end
    end
    if total == 0 then return false end
    if not sequence and active > 0 then
        local target = M.context()
        if not target then return false end
        sequence = {start=time, max=0, positions={}, bad=false, target=target}
    end
    local s = sequence
    if not s then return false end
    s.max = math.max(s.max, active)
    for _, touch in ipairs(touches) do
        if touch.type == 'indirect' and not touch.resting then
            local p, origin = touch.normalizedPosition, s.positions[touch.identity]
            if p and origin and ((p.x-origin.x)^2 + (p.y-origin.y)^2) > 0.0036 then s.bad = true end
            if p and not origin then s.positions[touch.identity] = {x=p.x,y=p.y} end
            if touch.phase == 'cancelled' then s.bad = true end
        end
    end
    if active > 3 or not M.sameTarget(s.target) then s.bad = true end
    local consume = s.max == 3 and not s.bad
    if active == 0 then
        sequence = nil
        if consume and not s.fired and time-s.start <= 0.65 then deferredMenu('Paste', s.target) end
    end
    return consume
end

function M.handle(event)
    local kind, flags = event:getType(), event:getFlags()
    if kind == types.leftMouseDown then
        mouseLink = nil
        if flags.ctrl and not flags.cmd and not flags.alt and not flags.shift and M.context(event, true) then
            mouseLink = true
            event:setFlags({cmd=true})
            return false
        end
    elseif mouseLink and (kind == types.leftMouseUp or kind == types.leftMouseDragged) then
        event:setFlags({cmd=true})
        if kind == types.leftMouseUp then mouseLink = nil end
        return false
    end
    if M.options.linksOnly then return false end
    if kind == types.keyUp then
        local consumed = M.releases[event:getKeyCode()]
        M.releases[event:getKeyCode()] = nil
        return consumed == true
    elseif kind == types.keyDown then
        local key = event:getKeyCode()
        local copy = key == hs.keycodes.map.c
        local paste = key == hs.keycodes.map.v
        local digit
        for i=0,9 do if key == hs.keycodes.map[tostring(i)] then digit=tostring(i) end end
        if flags.ctrl and flags.shift and not flags.cmd and not flags.alt and (copy or paste) then
            local target = M.context(event)
            if not target then return false end
            M.releases[key] = true
            deferredMenu(copy and 'Copy' or 'Paste', target)
            return true
        elseif flags.ctrl and flags.alt and not flags.cmd and not flags.shift and digit then
            local target = M.context(event)
            if not target then return false end
            M.releases[key] = true
            local app = hs.application.applicationForPID(target.pid)
            hs.eventtap.keyStroke({'ctrl'}, 'a', 0, app)
            hs.eventtap.keyStroke({}, digit, 0, app)
            return true
        end
    elseif kind == types.otherMouseDown and event:getProperty(props.mouseEventButtonNumber) == 2 then
        local target = M.context(event, true)
        if not M.sameTarget(target) then return false end
        middleDown = true
        deferredMenu('Paste', target)
        return true
    elseif kind == types.otherMouseUp and middleDown then
        middleDown = nil
        return true
    elseif kind == types.gesture then
        return M.feed(event:getTouches() or {}, now())
    elseif sequence and sequence.max == 3 and not sequence.bad and now()-sequence.start < 1.5 then
        if kind == types.leftMouseDown or kind == types.leftMouseUp then
            if kind == types.leftMouseDown and not sequence.fired then
                sequence.fired = true
                deferredMenu('Paste', sequence.target)
            end
            return true
        end
    end
    return false
end

function M.stop()
    for _, name in ipairs({'tap','health','wake','wakeTimer'}) do
        if M[name] then M[name]:stop(); M[name]=nil end
    end
    if M.toggle then M.toggle:delete(); M.toggle=nil end
    M.releases = {}
    sequence, mouseLink, middleDown = nil, nil, nil
end

function M.start(options)
    M.stop()
    M.options = options or {}
    if not hs.accessibilityState(true) then
        hs.alert.show('Awesome Byobu: allow Accessibility, then Reload Config')
        return M
    end
    local function recreate()
        if M.tap then M.tap:stop() end
        sequence, mouseLink, middleDown = nil, nil, nil
        M.releases = {}
        M.tap = hs.eventtap.new({types.keyDown,types.keyUp,types.leftMouseDown,types.leftMouseUp,
            types.leftMouseDragged,types.otherMouseDown,types.otherMouseUp,types.gesture}, M.handle):start()
    end
    recreate()
    M.health = hs.timer.doEvery(5, function()
        if not M.tap:isEnabled() and not hs.eventtap.isSecureInputEnabled() then recreate() end
    end)
    M.wake = hs.caffeinate.watcher.new(function(event)
        if event == hs.caffeinate.watcher.systemDidWake then
            if M.wakeTimer then M.wakeTimer:stop() end
            M.wakeTimer = hs.timer.doAfter(2, recreate)
        end
    end):start()
    if not M.options.linksOnly then
        M.toggle = hs.hotkey.bind({'ctrl'}, '`', function()
            local app = hs.application.get(iterm)
            if app and M.context() then app:hide()
            elseif app and #app:allWindows() > 0 then app:activate()
            else
                M.openTask = hs.task.new(os.getenv('HOME')..'/.local/bin/open-terminal-setup',
                    function() M.openTask=nil end):start()
            end
        end)
        hs.autoLaunch(true)
    end
    return M
end

return M
