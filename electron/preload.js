const { contextBridge, ipcRenderer } = require("electron");

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
    return ipcRenderer.invoke("generate-audio", payload);
  },
  generateIndexTTS2(payload) {
    return ipcRenderer.invoke("generate-indextts2", payload);
  },
  getRuntimeBackends() {
    return ipcRenderer.invoke("get-runtime-backends");
  },
  createGenerationJob(payload) {
    return ipcRenderer.invoke("create-generation-job", payload);
  },
  listGenerationJobs() {
    return ipcRenderer.invoke("list-generation-jobs");
  },
  getGenerationJob(payload) {
    return ipcRenderer.invoke("get-generation-job", payload);
  },
  cancelGenerationJob(payload) {
    return ipcRenderer.invoke("cancel-generation-job", payload);
  },
  retryGenerationJob(payload) {
    return ipcRenderer.invoke("retry-generation-job", payload);
  },
  listGenerationTakes(payload) {
    return ipcRenderer.invoke("list-generation-takes", payload);
  },
  selectGenerationTake(payload) {
    return ipcRenderer.invoke("select-generation-take", payload);
  },
  mediaUrl(projectRelativePath) {
    return ipcRenderer.sendSync("media-url", projectRelativePath);
  },
  listVoices(payload = {}) {
    return ipcRenderer.invoke("app-service", { action: "list-voices", payload });
  },
  createVoice(payload) {
    return ipcRenderer.invoke("app-service", { action: "create-voice", payload });
  },
  updateVoice(payload) {
    return ipcRenderer.invoke("app-service", { action: "update-voice", payload });
  },
  deleteVoice(payload) {
    return ipcRenderer.invoke("app-service", { action: "delete-voice", payload });
  },
  listGenerations(payload = {}) {
    return ipcRenderer.invoke("app-service", { action: "list-generations", payload });
  },
  createGeneration(payload) {
    return ipcRenderer.invoke("app-service", { action: "create-generation", payload });
  },
  markGenerationRunning(payload) {
    return ipcRenderer.invoke("app-service", { action: "mark-generation-running", payload });
  },
  markGenerationSucceeded(payload) {
    return ipcRenderer.invoke("app-service", { action: "mark-generation-succeeded", payload });
  },
  markGenerationFailed(payload) {
    return ipcRenderer.invoke("app-service", { action: "mark-generation-failed", payload });
  },
  deleteGeneration(payload) {
    return ipcRenderer.invoke("app-service", { action: "delete-generation", payload });
  },
});
