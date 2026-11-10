import { contextBridge, ipcRenderer } from "electron";
const channels=[
 "auth:state","auth:setup","auth:login","auth:logout","users:create",
 "models:list","models:import","models:test","models:enable","models:delete",
 "docs:list","docs:import","docs:chunks","docs:open","docs:reindex",
 "conversations:list","conversations:create","conversations:messages",
 "conversations:rename","conversations:delete","chat:ask","chat:cancel",
 "settings:status","settings:searchKey","settings:preferences","settings:preferences:update",
 "web:open","diagnostic:uiReady"
] as const;
type Channel=typeof channels[number];
interface ChunkEvent{requestId:string;conversationId:number;chunk:string}
contextBridge.exposeInMainWorld("ephraim",{
 invoke:(channel:Channel,...args:unknown[])=>{
  if(!channels.includes(channel))throw new Error("Unrecognised operation");
  return ipcRenderer.invoke(channel,...args);
 },
 onChunk:(callback:(message:ChunkEvent)=>void)=>{
  if(typeof callback!=="function")throw new Error("Invalid listener");
  const listener=(_event:Electron.IpcRendererEvent,data:unknown)=>{
    if(data&&typeof data==="object"){
      const x=data as Partial<ChunkEvent>;
      if(typeof x.requestId==="string"&&typeof x.conversationId==="number"&&typeof x.chunk==="string")callback({requestId:x.requestId,conversationId:x.conversationId,chunk:x.chunk});
    }
  };
  ipcRenderer.on("chat:chunk",listener);
  return ()=>ipcRenderer.removeListener("chat:chunk",listener);
 }
});
