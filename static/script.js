const conversation = document.getElementById("conversation");
const input = document.getElementById("messageInput");
const sendButton = document.getElementById("sendBtn");
const recordButton = document.getElementById("recordBtn");
const recordStatus = document.getElementById("recordStatus");
const inputLanguage = document.getElementById("inputLanguage");
const outputLanguage = document.getElementById("outputLanguage");
const voiceMic = document.getElementById("voiceMic");
const voiceOrb = document.getElementById("voiceOrb");
const voiceStatus = document.getElementById("voiceStatus");
const voiceStateChip = document.getElementById("voiceStateChip");
const recognizedText = document.getElementById("recognizedText");
const voiceError = document.getElementById("voiceError");
const replayVoice = document.getElementById("replayVoice");
const languagePrompt = document.getElementById("languagePrompt");
const languagePanel = document.getElementById("languagePanel");
const quickInputLanguage = document.getElementById("quickInputLanguage");
const selectedInputLanguage = document.getElementById("selectedInputLanguage");
const selectedVoiceLanguage = document.getElementById("selectedVoiceLanguage");
const confirmVoice = document.getElementById("confirmVoice");
const retryVoice = document.getElementById("retryVoice");
let recorder;
let recordingStream;
let audioChunks = [];
let lastAudioUrl = "";
let answerAudio;
let voiceRequestController;
let voiceState = "idle";
let cancelRecording = false;
let isBusy = false;

const languageNames = {
    auto: "Auto Detect",
    "te-IN": "Telugu",
    "en-IN": "English",
    "hi-IN": "Hindi",
    tenglish: "Tenglish",
    same: "Same as input"
};
const initialConversation = conversation.innerHTML;

function savePreferences() {
    sessionStorage.setItem("campusInputLanguage", inputLanguage.value);
    sessionStorage.setItem("campusOutputLanguage", outputLanguage.value);
}

function loadPreferences() {
    inputLanguage.value = sessionStorage.getItem("campusInputLanguage") || "auto";
    outputLanguage.value = sessionStorage.getItem("campusOutputLanguage") || "same";
    updateLanguageSummary();
}

function updateLanguageSummary() {
    document.getElementById("chatLanguageSummary").textContent =
        `${languageNames[inputLanguage.value]} \u2192 ${languageNames[outputLanguage.value]}`;
    selectedInputLanguage.textContent = `Selected: ${languageNames[inputLanguage.value]}`;
    selectedVoiceLanguage.textContent = `Input language: ${languageNames[inputLanguage.value]}`;
    quickInputLanguage.value = inputLanguage.value;
}

function showView(viewName) {
    document.querySelectorAll(".view").forEach(view => view.classList.toggle("active", view.id === `${viewName}View`));
    document.querySelectorAll(".nav-button").forEach(button => button.classList.toggle("active", button.dataset.view === viewName));
    window.scrollTo({top: 0, behavior: "auto"});
}

function addMessage(text, role, label, audioUrl = "") {
    const message = document.createElement("div");
    message.className = `message ${role}-message`;
    const icon = role === "user" ? "fa-user" : "fa-sparkles";
    message.innerHTML = `<div class="message-avatar"><i class="fa-solid ${icon}"></i></div>
        <div class="message-bubble"><span class="message-label"></span><p></p></div>`;
    message.querySelector(".message-label").textContent = label;
    message.querySelector("p").textContent = text;
    if (audioUrl) {
        const audio = document.createElement("audio");
        audio.controls = true;
        audio.preload = "none";
        audio.src = audioUrl;
        message.querySelector(".message-bubble").appendChild(audio);
    }
    conversation.appendChild(message);
    conversation.scrollTop = conversation.scrollHeight;
    sessionStorage.setItem("campusConversation", conversation.innerHTML);
    return message;
}

function addTyping() {
    const message = document.createElement("div");
    message.className = "message assistant-message";
    message.id = "typingMessage";
    message.innerHTML = `<div class="message-avatar"><i class="fa-solid fa-sparkles"></i></div>
        <div class="message-bubble"><span class="message-label">CampusVoice AI \u00b7 Preparing your answer</span>
        <div class="typing"><i></i><i></i><i></i></div></div>`;
    conversation.appendChild(message);
    conversation.scrollTop = conversation.scrollHeight;
}

function setBusy(value) {
    isBusy = value;
    sendButton.disabled = value;
    recordButton.disabled = value;
    input.disabled = value;
}

function showError(message) {
    addMessage(message, "assistant", "CampusVoice AI \u00b7 Notice");
}

async function submitText(question) {
    if (isBusy || !question.trim()) return;
    showView("chat");
    addMessage(question.trim(), "user", "You \u00b7 Just now");
    input.value = "";
    input.style.height = "auto";
    addTyping();
    setBusy(true);
    recordStatus.textContent = "Preparing...";
    try {
        const response = await fetch("/api/text", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                question: question.trim(),
                input_language: inputLanguage.value,
                output_language: outputLanguage.value
            })
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || "Unable to answer");
        addMessage(data.answer, "assistant", `CampusVoice AI \u00b7 ${languageNames[data.output_language]}`, data.audio_url);
    } catch (error) {
        showError(error.message);
    } finally {
        document.getElementById("typingMessage")?.remove();
        setBusy(false);
        recordStatus.textContent = "Ready";
    }
}

function setVoiceState(state, message) {
    voiceState = state.toLowerCase().replace(" ", "_");
    voiceStateChip.textContent = state;
    voiceStatus.textContent = message;
    voiceOrb.className = `voice-orb ${state.toLowerCase().replace(" ", "-")}`;
}

function stopRecordingStream() {
    recordingStream?.getTracks().forEach(track => track.stop());
    recordingStream = undefined;
}

function stopAnswerAudio() {
    if (!answerAudio) return;
    answerAudio.pause();
    answerAudio.currentTime = 0;
    answerAudio = undefined;
    setVoiceState("Idle", "Tap the microphone to start");
}

function resetVoice({clearTranscript = true} = {}) {
    voiceRequestController?.abort();
    voiceRequestController = undefined;
    if (recorder && recorder.state !== "inactive") {
        cancelRecording = true;
        recorder.stop();
    }
    stopRecordingStream();
    stopAnswerAudio();
    audioChunks = [];
    lastAudioUrl = "";
    cancelRecording = false;
    setVoiceState("Idle", "Tap the microphone to start");
    if (clearTranscript) recognizedText.textContent = "Your question will appear here";
    voiceError.textContent = "";
    voiceMic.innerHTML = '<i class="fa-solid fa-microphone"></i>';
    voiceMic.disabled = false;
    replayVoice.disabled = true;
    replayVoice.classList.remove("playing");
    confirmVoice.disabled = true;
    selectedVoiceLanguage.textContent = `Input language: ${languageNames[inputLanguage.value]}`;
}

async function toggleVoiceRecording() {
    if (isBusy) return;
    if (recorder?.state === "recording") {
        setVoiceState("Transcribing", "Preparing your recording...");
        recorder.stop();
        return;
    }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
        const message = "Voice recording is not supported in this browser.";
        voiceError.textContent = message;
        return;
    }
    try {
        recordingStream = await navigator.mediaDevices.getUserMedia({audio: true});
        const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
        recorder = new MediaRecorder(recordingStream, mimeType ? {mimeType} : undefined);
        audioChunks = [];
        cancelRecording = false;
        recorder.ondataavailable = event => { if (event.data.size) audioChunks.push(event.data); };
        recorder.onstop = () => {
            stopRecordingStream();
            if (!cancelRecording) transcribeVoiceRecording();
        };
        recorder.start();
        setVoiceState("Recording", inputLanguage.value === "tenglish" ? "Listening for Telugu-English code-mixed speech..." : "Listening to your question...");
        voiceMic.innerHTML = '<i class="fa-solid fa-stop"></i>';
        voiceMic.classList.add("recording");
    } catch (error) {
        const message = "Microphone access was not granted. Please check browser permissions.";
        voiceError.textContent = message;
        setVoiceState("Error", message);
    }
}

async function transcribeVoiceRecording() {
    setVoiceState("Transcribing", "Understanding your question...");
    voiceMic.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
    voiceMic.disabled = true;
    const type = audioChunks[0]?.type || "audio/webm";
    const extension = type.includes("ogg") ? "ogg" : "webm";
    const formData = new FormData();
    formData.append("audio", new Blob(audioChunks, {type}), `recording.${extension}`);
    formData.append("input_language", inputLanguage.value);
    formData.append("transcribe_only", "true");
    try {
        voiceRequestController = new AbortController();
        const response = await fetch("/api/ask", {
            method: "POST",
            body: formData,
            signal: voiceRequestController.signal
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || "Unable to process recording");
        recognizedText.textContent = data.transcript;
        setVoiceState("Transcript ready", "Review your question, then ask CampusVoice AI");
        confirmVoice.disabled = false;
        voiceMic.disabled = false;
        voiceMic.classList.remove("recording");
        voiceMic.innerHTML = '<i class="fa-solid fa-microphone"></i>';
    } catch (error) {
        if (error.name === "AbortError") return;
        setVoiceState("Error", "Something went wrong");
        voiceError.textContent = error.message;
        voiceMic.disabled = false;
        voiceMic.classList.remove("recording");
        voiceMic.innerHTML = '<i class="fa-solid fa-microphone"></i>';
    } finally {
        voiceRequestController = undefined;
    }
}

async function answerVoiceQuestion() {
    if (voiceState !== "transcript_ready" || !recognizedText.textContent.trim()) return;
    setVoiceState("Answering", "Preparing your campus answer...");
    confirmVoice.disabled = true;
    voiceMic.disabled = true;
    try {
        voiceRequestController = new AbortController();
        const response = await fetch("/api/text", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            signal: voiceRequestController.signal,
            body: JSON.stringify({
                question: recognizedText.textContent.trim(),
                input_language: inputLanguage.value,
                output_language: outputLanguage.value
            })
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || "Unable to answer");
        lastAudioUrl = data.audio_url;
        answerAudio = new Audio(lastAudioUrl);
        answerAudio.addEventListener("ended", () => {
            replayVoice.classList.remove("playing");
            setVoiceState("Answer ready", "Your answer is ready");
        });
        addMessage(data.transcript || recognizedText.textContent, "user", "You · Voice transcript");
        addMessage(data.answer, "assistant", "CampusVoice AI · Your answer", data.audio_url);
        setVoiceState("Answer ready", "Your answer is ready");
        replayVoice.disabled = false;
        voiceMic.disabled = false;
    } catch (error) {
        if (error.name === "AbortError") return;
        setVoiceState("Error", "Something went wrong");
        voiceError.textContent = error.message;
        confirmVoice.disabled = false;
    } finally {
        voiceRequestController = undefined;
    }

    function toggleRecording(source = "chat") {
        if (source !== "chat" || isBusy) return;
        if (recorder?.state === "recording") {
            recorder.stop();
            return;
        }
        if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
            showError("Voice recording is not supported in this browser.");
            return;
        }
        navigator.mediaDevices.getUserMedia({audio: true}).then(stream => {
            const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
            recorder = new MediaRecorder(stream, mimeType ? {mimeType} : undefined);
            audioChunks = [];
            recorder.ondataavailable = event => { if (event.data.size) audioChunks.push(event.data); };
            recorder.onstop = () => {
                stream.getTracks().forEach(track => track.stop());
                processRecording("chat");
            };
            recorder.start();
            recordButton.classList.add("recording");
            recordButton.innerHTML = '<i class="fa-solid fa-stop"></i>';
            recordStatus.textContent = "Listening...";
        }).catch(() => showError("Microphone access was not granted. Please check browser permissions."));
    }

    async function processRecording(source) {
        if (source !== "chat") return;
        recordButton.classList.remove("recording");
        recordButton.classList.add("processing");
        recordButton.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
        recordStatus.textContent = "Processing...";
        setBusy(true);
        const type = audioChunks[0]?.type || "audio/webm";
        const extension = type.includes("ogg") ? "ogg" : "webm";
        const formData = new FormData();
        formData.append("audio", new Blob(audioChunks, {type}), `recording.${extension}`);
        formData.append("input_language", inputLanguage.value);
        formData.append("output_language", outputLanguage.value);
        try {
            const response = await fetch("/api/ask", {method: "POST", body: formData});
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.error || "Unable to process recording");
            addMessage(data.transcript, "user", "You · Voice transcript");
            addMessage(data.answer, "assistant", "CampusVoice AI · Your answer", data.audio_url);
            recordStatus.textContent = "Answer ready";
        } catch (error) {
            showError(error.message);
            recordStatus.textContent = "Ready";
        } finally {
            setBusy(false);
            recordButton.classList.remove("processing");
            recordButton.innerHTML = '<i class="fa-solid fa-microphone"></i>';
        }
    }
}

function resetChat() {
    conversation.innerHTML = initialConversation;
    sessionStorage.removeItem("campusConversation");
    input.value = "";
    showView("chat");
    input.focus();
}

document.querySelectorAll("[data-view]").forEach(button => {
    button.addEventListener("click", () => {
        const view = button.dataset.view;
        showView(view);
        if (view === "voice") resetVoice();
    });
});
document.querySelectorAll("[data-question]").forEach(button => {
    button.addEventListener("click", () => {
        submitText(button.dataset.question);
    });
});
sendButton.addEventListener("click", () => submitText(input.value));
recordButton.addEventListener("click", () => toggleRecording("chat"));
voiceMic.addEventListener("click", toggleVoiceRecording);
document.getElementById("cancelVoice").addEventListener("click", () => {
    resetVoice();
    showView("home");
});
confirmVoice.addEventListener("click", answerVoiceQuestion);
replayVoice.addEventListener("click", () => {
    if (!answerAudio || !lastAudioUrl || voiceState === "recording" || voiceState === "transcribing" || voiceState === "answering") return;
    answerAudio.currentTime = 0;
    answerAudio.play().then(() => {
        replayVoice.classList.add("playing");
        setVoiceState("Playing", "Playing your answer...");
    }).catch(() => {
        voiceError.textContent = "Audio playback was blocked. Use the player in Smart Chat to replay it.";
    });
});
document.getElementById("homeMenu").addEventListener("click", () => {
    document.querySelector(".language-settings").scrollIntoView({behavior: "auto", block: "center"});
});
languagePrompt.addEventListener("click", () => {
    languagePanel.hidden = !languagePanel.hidden;
    if (!languagePanel.hidden) quickInputLanguage.focus();
});
quickInputLanguage.addEventListener("change", () => {
    inputLanguage.value = quickInputLanguage.value;
    savePreferences();
    updateLanguageSummary();
});
retryVoice.addEventListener("click", () => {
    resetVoice();
    voiceMic.focus();
});
document.getElementById("clearHistory").addEventListener("click", () => {
    sessionStorage.removeItem("campusConversation");
    document.getElementById("recentList").innerHTML = '<p class="empty-state">Your recent conversations will appear here.</p>';
});
document.getElementById("headerNewChat")?.addEventListener("click", resetChat);
inputLanguage.addEventListener("change", () => { savePreferences(); updateLanguageSummary(); });
outputLanguage.addEventListener("change", () => { savePreferences(); updateLanguageSummary(); });
input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 100)}px`;
});
input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        submitText(input.value);
    }
});

const savedConversation = sessionStorage.getItem("campusConversation");
if (savedConversation) conversation.innerHTML = savedConversation;
loadPreferences();
