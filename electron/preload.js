const { contextBridge, ipcRenderer } = require("electron");

async function invokeBackend(channel, ...args) {
  const result = await ipcRenderer.invoke(channel, ...args);
  if (result && result.ok === false && result.error) {
    return Promise.reject(result.error);
  }
  return result && result.ok === true ? result.value : result;
}

contextBridge.exposeInMainWorld("voxcpmShell", {
  onStatus(callback) {
    ipcRenderer.on("status", (_event, payload) => callback(payload));
  },
  getShellState() {
    return ipcRenderer.invoke("get-shell-state");
  },
  selectAudioFile() {
    return ipcRenderer.invoke("select-audio-file");
  },
  generateAudio(payload) {
    return invokeBackend("generate-audio", payload);
  },
  generateIndexTTS2(payload) {
    return invokeBackend("generate-indextts2", payload);
  },
  getRuntimeBackends() {
    return invokeBackend("get-runtime-backends");
  },
  getIndexTTS2RuntimeProfile() {
    return invokeBackend("get-indextts2-runtime-profile");
  },
  saveIndexTTS2RuntimeProfile(payload) {
    return invokeBackend("save-indextts2-runtime-profile", payload);
  },
  createGenerationJob(payload) {
    return invokeBackend("create-generation-job", payload);
  },
  listGenerationJobs() {
    return invokeBackend("list-generation-jobs");
  },
  getGenerationJob(payload) {
    return invokeBackend("get-generation-job", payload);
  },
  cancelGenerationJob(payload) {
    return invokeBackend("cancel-generation-job", payload);
  },
  retryGenerationJob(payload) {
    return invokeBackend("retry-generation-job", payload);
  },
  listGenerationTakes(payload) {
    return invokeBackend("list-generation-takes", payload);
  },
  selectGenerationTake(payload) {
    return invokeBackend("select-generation-take", payload);
  },
  getUpdateStatus(payload) {
    return ipcRenderer.invoke("get-update-status", payload);
  },
  preflightUpdate(payload) {
    return ipcRenderer.invoke("preflight-update", payload);
  },
  fetchUpdate(payload) {
    return ipcRenderer.invoke("fetch-update", payload);
  },
  applyUpdate(payload) {
    return ipcRenderer.invoke("apply-update", payload);
  },
  mediaUrl(projectRelativePath) {
    return ipcRenderer.sendSync("media-url", projectRelativePath);
  },
  listVoices(payload = {}) {
    return invokeBackend("app-service", { action: "list-voices", payload });
  },
  createVoice(payload) {
    return invokeBackend("app-service", { action: "create-voice", payload });
  },
  updateVoice(payload) {
    return invokeBackend("app-service", { action: "update-voice", payload });
  },
  deleteVoice(payload) {
    return invokeBackend("app-service", { action: "delete-voice", payload });
  },
  listGenerations(payload = {}) {
    return invokeBackend("app-service", { action: "list-generations", payload });
  },
  createGeneration(payload) {
    return invokeBackend("app-service", { action: "create-generation", payload });
  },
  markGenerationRunning(payload) {
    return invokeBackend("app-service", { action: "mark-generation-running", payload });
  },
  markGenerationSucceeded(payload) {
    return invokeBackend("app-service", { action: "mark-generation-succeeded", payload });
  },
  markGenerationFailed(payload) {
    return invokeBackend("app-service", { action: "mark-generation-failed", payload });
  },
  deleteGeneration(payload) {
    return invokeBackend("app-service", { action: "delete-generation", payload });
  },
  restoreGeneration(payload) {
    return invokeBackend("app-service", { action: "restore-generation", payload });
  },
  updateGenerationFavorite(payload) {
    return invokeBackend("app-service", { action: "update-generation-favorite", payload });
  },
  purgeGenerations(payload) {
    return invokeBackend("app-service", { action: "purge-generations", payload });
  },
  promoteGenerationToVoice(payload) {
    return invokeBackend("app-service", { action: "promote-generation-to-voice", payload });
  },
  exportAudioFile(payload) {
    return ipcRenderer.invoke("export-audio-file", payload);
  },
});
