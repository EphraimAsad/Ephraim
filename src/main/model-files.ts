import { lstatSync, realpathSync, renameSync, unlinkSync } from "node:fs";
import { basename, dirname, join, resolve, sep } from "node:path";
import { randomBytes } from "node:crypto";

/** Only files previously copied into Ephraim's own models folder can be deleted. */
export function validateOwnedModelPath(path:string,modelsDir:string):string {
  const target=resolve(path);
  const dir=resolve(modelsDir);
  if(dirname(target)!==dir || !/^[a-f0-9]{32}\.gguf$/.test(basename(target)))
    throw new Error("Model is not an Ephraim-managed GGUF copy");
  // Refuse junctions / symlinks, even if their apparent path is within the model directory.
  if(realpathSync(dir)!==dir || realpathSync(target)!==target || !lstatSync(target).isFile())
    throw new Error("Model path is not a regular managed file");
  return target;
}
/** Transaction compensation: callers must delete the DB row before removing the quarantined file. */
export function quarantineManagedModel(path:string,modelsDir:string):{commit:()=>void;rollback:()=>void} {
  const target=validateOwnedModelPath(path,modelsDir);
  const quarantine=join(dirname(target),".deleting-"+randomBytes(16).toString("hex"));
  renameSync(target,quarantine);
  return {
    commit:()=>unlinkSync(quarantine),
    rollback:()=>renameSync(quarantine,target)
  };
}
