local audioCheck = dofile(hs.configdir .. "/audio_check_impl.lua")
hs.hotkey.bind(AgentDesk.hyper, "ä", audioCheck.run)
