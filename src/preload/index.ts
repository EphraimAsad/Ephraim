import { contextBridge, ipcRenderer } from "electron";
const channels=["auth:state","auth:setup","auth:login","auth:logout","users:create","models:list","models:import","models:test","models:enable","docs:list","docs:import","chat:history","chat:ask","settings:status","settings:searchKey"] as const;
type Channel=typeof channels[number];
contextBridge.exposeInMainWorld("ephraim",{
  invoke:(channel:Channel,...args:unknown[])=>{
    if(!channels.includes(channel))throw new Error("Unsupported operation");
    return ipcRenderer.invoke(channel,...args);
  }
});
