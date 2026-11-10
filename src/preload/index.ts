import { contextBridge, ipcRenderer } from "electron";
const channels=[
 "auth:state","auth:setup","auth:login","auth:logout","users:create",
 "models:list","models:import","models:test","models:enable",
 "docs:list","docs:import","docs:chunks","docs:open","docs:reindex",
 "conversations:list","conversations:create","conversations:messages",
 "chat:ask","settings:status","settings:searchKey"
] as const;
type Channel=typeof channels[number];
contextBridge.exposeInMainWorld("ephraim",{
 invoke:(channel:Channel,...args:unknown[])=>{
  if(!channels.includes(channel))throw new Error("Unrecognised operation");
  return ipcRenderer.invoke(channel,...args);
 }
});
