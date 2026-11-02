-- Pure Lua: no real key events, clipboard access, or running Hammerspoon required.
local keys = {c=8,v=9,a=0}
for i=0,9 do keys[tostring(i)]=20+i end
local types = {keyDown=1,keyUp=2,leftMouseDown=3,leftMouseUp=4,leftMouseDragged=5,
    otherMouseDown=6,otherMouseUp=7,gesture=8}
local props = {mouseEventButtonNumber=1,mouseEventWindowUnderMousePointerThatCanHandleThisEvent=2,
    mouseEventWindowUnderMousePointer=3}
local currentPID, currentID, menuCount, keyCount = 1, 10, 0, 0
local deferred = {}
local apps = {
    [1]={bundleID=function() return 'com.googlecode.iterm2' end,
        selectMenuItem=function() menuCount=menuCount+1; return true end},
    [2]={bundleID=function() return 'com.google.Chrome' end},
}
hs = {
    keycodes={map=keys},
    eventtap={event={types=types,properties=props},keyStroke=function() keyCount=keyCount+1 end},
    application={applicationForPID=function(pid) return apps[pid] end},
    window={list=function() return {{kCGWindowOwnerPID=currentPID,kCGWindowNumber=currentID,
        kCGWindowIsOnscreen=true,kCGWindowAlpha=1,kCGWindowBounds={Width=1000,Height=800}}} end},
    timer={absoluteTime=function() return 0 end,doAfter=function(_,callback) table.insert(deferred,callback) end},
}
local module = dofile('platforms/macos/hammerspoon/init.lua')
module.options = {}
local function event(kind,code,flags,button)
    local e={kind=kind,code=code,flags=flags or {}}
    function e:getType() return self.kind end
    function e:getKeyCode() return self.code end
    function e:getFlags() return self.flags end
    function e:setFlags(flags) self.flags=flags end
    function e:getProperty(property) return property==1 and (button or 0) or currentID end
    return e
end
local function flush()
    local pending=deferred; deferred={}
    for _, callback in ipairs(pending) do callback() end
end
local click=event(types.leftMouseDown,0,{ctrl=true})
assert(not module.handle(click) and click.flags.cmd, 'Ctrl-click must become native Cmd-click')
local release=event(types.leftMouseUp,0,{})
assert(not module.handle(release) and release.flags.cmd, 'release retains mapped modifier')
currentPID=2
click=event(types.leftMouseDown,0,{ctrl=true})
assert(not module.handle(click) and not click.flags.cmd, 'browser Ctrl-click remains untouched')
currentPID=1
assert(not module.handle(event(types.keyDown,keys.c,{ctrl=true})), 'Ctrl-C must stay interrupt')
assert(module.handle(event(types.keyDown,keys.v,{ctrl=true,shift=true})), 'Ctrl-Shift-V consumed')
assert(module.handle(event(types.keyUp,keys.v,{})), 'key up consumed after modifiers released')
flush(); assert(menuCount==1, 'one native paste')
assert(module.handle(event(types.otherMouseDown,0,{},2)), 'middle down consumed')
assert(module.handle(event(types.otherMouseUp,0,{},2)), 'middle up consumed')
currentID=11; flush(); assert(menuCount==1, 'focus change cancels paste')
currentID=10
assert(module.handle(event(types.keyDown,keys['3'],{ctrl=true,alt=true})), 'direct Byobu tab')
assert(keyCount==2, 'prefix and digit only')
assert(module.handle(event(types.keyUp,keys['3'],{})))
local function touches(active, x, count)
    local result={}
    for i=1,(count or 3) do result[i]={type='indirect',identity=i,touching=active,
        normalizedPosition={x=x or 0.1,y=0.1}} end
    return result
end
assert(module.feed(touches(true),0))
assert(module.feed(touches(false),0.2))
flush(); assert(menuCount==2, 'three-finger tap pastes once')
module.feed(touches(true),1); module.feed(touches(true,0.8),1.1); module.feed(touches(false,0.8),1.2)
flush(); assert(menuCount==2, 'swipe must not paste')
module.feed(touches(true,0.1,4),2); module.feed(touches(false,0.1,4),2.2)
flush(); assert(menuCount==2, 'four fingers must not paste')
currentPID=2
assert(not module.feed(touches(true),3), 'gesture outside terminal passes through')
assert(not module.handle(event(types.keyDown,keys.v,{ctrl=true,shift=true})), 'browser paste unchanged')
currentPID=1
module.options={linksOnly=true}
assert(not module.handle(event(types.otherMouseDown,0,{},2)), 'migration leaves existing paste ownership')
print('Hammerspoon routing passed: terminal-only keys, clicks, focus changes, and gestures')
