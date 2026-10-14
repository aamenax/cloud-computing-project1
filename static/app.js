/**
 * Voice Command Recognition - Modern Frontend Controller
 * Uses Web Speech API (Live Speech Recognition) + Web Audio API (PCM Downsampling & Waveform)
 * Supports full interactive Voice Commands with real-time feedback and speech response.
 */

let audioContext = null;
let mediaStream = null;
let audioInput = null;
let scriptProcessor = null;
let analyser = null;
let isRecording = false;
let audioChunks = [];
let speechRecognizer = null;
let currentLiveTranscript = '';

// DOM Elements
const micBtn = document.getElementById('micBtn');
const recordingStatus = document.getElementById('recordingStatus');
const voiceInstruction = document.getElementById('voiceInstruction');
const canvas = document.getElementById('waveformCanvas');
const canvasCtx = canvas.getContext('2d');
const textInput = document.getElementById('textCommandInput');
const sendTextBtn = document.getElementById('sendTextBtn');
const cloudStatusText = document.getElementById('cloudStatusText');
const transcriptDisplay = document.getElementById('transcriptDisplay');
const intentName = document.getElementById('intentName');
const confidenceTag = document.getElementById('confidenceTag');
const slotsContainer = document.getElementById('slotsContainer');
const fulfillmentMessage = document.getElementById('fulfillmentMessage');
const pollyAudio = document.getElementById('pollyAudio');
const latencyBadge = document.getElementById('latencyBadge');
const rawJsonViewer = document.getElementById('rawJsonViewer');
const sampleChips = document.querySelectorAll('.chip');

// Initialize Waveform Canvas
function drawIdleWaveform() {
    canvasCtx.clearRect(0, 0, canvas.width, canvas.height);
    canvasCtx.lineWidth = 2;
    canvasCtx.strokeStyle = 'rgba(100, 116, 139, 0.35)';
    canvasCtx.beginPath();
    const sliceWidth = canvas.width / 50;
    let x = 0;
    for (let i = 0; i < 50; i++) {
        const y = canvas.height / 2 + Math.sin(i * 0.4) * 2;
        if (i === 0) canvasCtx.moveTo(x, y);
        else canvasCtx.lineTo(x, y);
        x += sliceWidth;
    }
    canvasCtx.stroke();
}
drawIdleWaveform();

// Setup Web Speech Recognition (Built-in Browser Engine)
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SpeechRecognition) {
    speechRecognizer = new SpeechRecognition();
    speechRecognizer.continuous = false;
    speechRecognizer.interimResults = true;
    speechRecognizer.lang = 'en-US';

    speechRecognizer.onresult = (event) => {
        let interimTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
            const transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
                currentLiveTranscript = transcript;
            } else {
                interimTranscript += transcript;
            }
        }
        const activeText = currentLiveTranscript || interimTranscript;
        if (activeText) {
            transcriptDisplay.textContent = `"${activeText}"`;
            voiceInstruction.innerHTML = `Heard: <em>"${activeText}"</em>`;
        }
    };

    speechRecognizer.onerror = (event) => {
        console.warn('Speech recognition notice:', event.error);
    };

    speechRecognizer.onend = () => {
        if (isRecording) {
            stopRecording();
        }
    };
}

// Start Voice Recording
async function startRecording() {
    try {
        currentLiveTranscript = '';
        audioChunks = [];

        // Request microphone access
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        mediaStream = stream;

        // Initialize AudioContext at hardware sample rate to avoid driver errors
        const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
        audioContext = new AudioCtxClass();
        if (audioContext.state === 'suspended') {
            await audioContext.resume();
        }

        audioInput = audioContext.createMediaStreamSource(stream);
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;

        scriptProcessor = audioContext.createScriptProcessor(4096, 1, 1);
        scriptProcessor.onaudioprocess = (e) => {
            if (!isRecording) return;
            const channelData = e.inputBuffer.getChannelData(0);
            audioChunks.push(new Float32Array(channelData));
        };

        audioInput.connect(analyser);
        analyser.connect(scriptProcessor);
        scriptProcessor.connect(audioContext.destination);

        isRecording = true;
        micBtn.classList.add('recording');
        recordingStatus.textContent = 'Listening (Speak now)...';
        recordingStatus.style.background = 'rgba(239, 68, 68, 0.2)';
        recordingStatus.style.color = '#ef4444';
        voiceInstruction.textContent = 'Listening to your voice... Speak your command!';
        cloudStatusText.textContent = 'Capturing Voice Stream...';

        // Start Web Speech Engine for real-time transcription
        if (speechRecognizer) {
            try {
                speechRecognizer.start();
            } catch (e) {
                console.log('SpeechRecognizer already active or restarting:', e);
            }
        }

        visualize();
    } catch (err) {
        console.error('Microphone access denied or error:', err);
        alert('Microphone Access Error: ' + err.message + '\n\nPlease ensure your browser allows microphone access on http://127.0.0.1:5000.');
        recordingStatus.textContent = 'Mic Blocked';
        voiceInstruction.textContent = 'Microphone permission blocked. Please enable it in browser settings.';
    }
}

// Stop Recording & Send Command
async function stopRecording() {
    if (!isRecording) return;
    isRecording = false;

    micBtn.classList.remove('recording');
    recordingStatus.textContent = 'Evaluating with AWS Lex...';
    recordingStatus.style.background = 'rgba(255, 153, 0, 0.2)';
    recordingStatus.style.color = '#ff9900';
    cloudStatusText.textContent = 'Processing Intent...';

    if (speechRecognizer) {
        try { speechRecognizer.stop(); } catch (e) {}
    }

    // Disconnect audio nodes
    if (scriptProcessor) scriptProcessor.disconnect();
    if (audioInput) audioInput.disconnect();
    if (mediaStream) mediaStream.getTracks().forEach(track => track.stop());

    // Resample recorded audio to 16kHz Mono PCM WAV
    const originalRate = audioContext ? audioContext.sampleRate : 44100;
    const wavBlob = encodeResampledWAV(audioChunks, originalRate, 16000);
    drawIdleWaveform();

    // Prepare payload
    const formData = new FormData();
    formData.append('audio', wavBlob, 'command.wav');
    if (currentLiveTranscript) {
        formData.append('transcript', currentLiveTranscript);
    }

    try {
        const response = await fetch('/api/command/voice', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        handleServerResult(result);
    } catch (err) {
        console.error('Voice processing error:', err);
        fulfillmentMessage.textContent = 'Error: ' + err.message;
    } finally {
        recordingStatus.textContent = 'Standby';
        recordingStatus.style.background = 'rgba(148, 163, 184, 0.15)';
        recordingStatus.style.color = '#94a3b8';
        voiceInstruction.innerHTML = 'Click microphone and say: <em>"Turn on the bedroom fan"</em> or <em>"Set AC to 22"</em>';
        cloudStatusText.textContent = 'Ready for Voice Input';
    }
}

// Real-time Canvas Waveform Visualizer
function visualize() {
    if (!isRecording) return;
    requestAnimationFrame(visualize);

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    analyser.getByteTimeDomainData(dataArray);

    canvasCtx.fillStyle = '#090d16';
    canvasCtx.fillRect(0, 0, canvas.width, canvas.height);

    canvasCtx.lineWidth = 2.5;
    canvasCtx.strokeStyle = '#ff9900';
    canvasCtx.beginPath();

    const sliceWidth = canvas.width / bufferLength;
    let x = 0;

    for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 128.0;
        const y = (v * canvas.height) / 2;
        if (i === 0) canvasCtx.moveTo(x, y);
        else canvasCtx.lineTo(x, y);
        x += sliceWidth;
    }

    canvasCtx.lineTo(canvas.width, canvas.height / 2);
    canvasCtx.stroke();
}

// Mic Click Handler
micBtn.addEventListener('click', () => {
    if (!isRecording) {
        startRecording();
    } else {
        stopRecording();
    }
});

// Text Fallback Command Handler
async function sendTextCommand(cmdText) {
    const text = (cmdText || textInput.value || '').trim();
    if (!text) return;

    recordingStatus.textContent = 'Querying AWS Lex...';
    transcriptDisplay.textContent = `"${text}"`;
    cloudStatusText.textContent = 'Evaluating Intent...';

    try {
        const response = await fetch('/api/command/text', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        const result = await response.json();
        handleServerResult(result);
    } catch (err) {
        console.error('Text command error:', err);
        fulfillmentMessage.textContent = 'Error: ' + err.message;
    } finally {
        recordingStatus.textContent = 'Standby';
        cloudStatusText.textContent = 'Ready for Voice Input';
        textInput.value = '';
    }
}

sendTextBtn.addEventListener('click', () => sendTextCommand());
textInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendTextCommand();
});

// Sample command chips
sampleChips.forEach(chip => {
    chip.addEventListener('click', () => {
        const cmd = chip.getAttribute('data-cmd');
        sendTextCommand(cmd);
    });
});

// Update UI & Play Audio
function handleServerResult(result) {
    if (result.status !== 'success') {
        fulfillmentMessage.textContent = '❌ ' + (result.message || 'Recognition error.');
        rawJsonViewer.textContent = JSON.stringify(result, null, 2);
        return;
    }

    // 1. Update ASR Transcript
    transcriptDisplay.textContent = `"${result.transcript || 'None'}"`;

    // 2. Update Intent & Confidence
    intentName.textContent = result.intent || 'UnknownIntent';
    confidenceTag.textContent = result.confidence ? `Confidence: ${(result.confidence * 100).toFixed(0)}%` : 'Confidence: 100%';

    // 3. Update Slots
    slotsContainer.innerHTML = '';
    const slots = result.slots || {};
    const slotKeys = Object.keys(slots);
    if (slotKeys.length === 0 || !slotKeys.some(k => slots[k])) {
        slotsContainer.innerHTML = '<span class="empty-state">No slots detected</span>';
    } else {
        slotKeys.forEach(k => {
            if (slots[k]) {
                const tag = document.createElement('span');
                tag.className = 'slot-tag';
                tag.innerHTML = `<strong>${k}:</strong> ${slots[k]}`;
                slotsContainer.appendChild(tag);
            }
        });
    }

    // 4. Update Fulfillment Message & Voice Output
    fulfillmentMessage.textContent = `"${result.message}"`;
    if (result.audio_base64) {
        // Amazon Polly Voice Stream from AWS
        pollyAudio.src = `data:audio/mp3;base64,${result.audio_base64}`;
        pollyAudio.style.display = 'block';
        pollyAudio.play().catch(e => console.log('Autoplay prevented:', e));
    } else {
        pollyAudio.style.display = 'none';
        // Speak response using browser speech synthesis for full voice feedback
        if ('speechSynthesis' in window && result.message) {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(result.message);
            utterance.rate = 1.0;
            window.speechSynthesis.speak(utterance);
        }
    }

    // 5. Update Latency Badge
    latencyBadge.textContent = `RTT: ${result.latency_ms || 0} ms`;

    // 6. Update Virtual Devices
    if (result.device_states) {
        updateDeviceVisuals(result.device_states);
    }

    // 7. Update Raw JSON Payload
    rawJsonViewer.textContent = JSON.stringify(result.raw_lex_response || result, null, 2);
}

// Update Visual State of Smart Devices
function updateDeviceVisuals(devices) {
    Object.keys(devices).forEach(devId => {
        const dev = devices[devId];
        const el = document.getElementById(`device-${devId}`);
        if (!el) return;

        const pill = el.querySelector('.device-state-pill');
        const isActive = dev.state === 'on' || dev.state === 'unlocked';

        if (isActive) {
            el.classList.add('active');
        } else {
            el.classList.remove('active');
        }

        if (dev.type === 'light') {
            pill.className = `device-state-pill ${dev.state}`;
            pill.textContent = dev.state.toUpperCase();
        } else if (dev.type === 'fan') {
            pill.className = `device-state-pill ${dev.state}`;
            pill.textContent = dev.state === 'on' ? 'SPINNING' : 'OFF';
        } else if (dev.type === 'ac') {
            pill.className = `device-state-pill ${dev.state}`;
            pill.textContent = dev.state === 'on' ? `COOLING (${dev.temp || 22}°C)` : `OFF (${dev.temp || 24}°C)`;
        } else if (dev.type === 'lock') {
            pill.className = `device-state-pill ${dev.state}`;
            pill.textContent = dev.state.toUpperCase();
        }
    });
}

// Fetch Initial Device States on Load
async function fetchInitialDevices() {
    try {
        const res = await fetch('/api/devices');
        const data = await res.json();
        if (data.devices) updateDeviceVisuals(data.devices);
    } catch (e) {
        console.warn('Could not load initial devices:', e);
    }
}
fetchInitialDevices();

// Resample audio samples and encode to 16kHz 16-bit Mono PCM WAV
function encodeResampledWAV(samplesArrays, sourceRate, targetRate) {
    let totalLength = 0;
    samplesArrays.forEach(arr => totalLength += arr.length);
    const merged = new Float32Array(totalLength);
    let offset = 0;
    samplesArrays.forEach(arr => {
        merged.set(arr, offset);
        offset += arr.length;
    });

    // Linear downsampling to targetRate (16000Hz)
    let resampled;
    if (sourceRate === targetRate || totalLength === 0) {
        resampled = merged;
    } else {
        const ratio = sourceRate / targetRate;
        const newLength = Math.round(totalLength / ratio);
        resampled = new Float32Array(newLength);
        for (let i = 0; i < newLength; i++) {
            const srcIndex = i * ratio;
            const floor = Math.floor(srcIndex);
            const ceil = Math.min(floor + 1, totalLength - 1);
            const interp = srcIndex - floor;
            resampled[i] = (1 - interp) * merged[floor] + interp * merged[ceil];
        }
    }

    const buffer = new ArrayBuffer(44 + resampled.length * 2);
    const view = new DataView(buffer);

    // RIFF Chunk
    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + resampled.length * 2, true);
    writeString(view, 8, 'WAVE');

    // fmt Chunk
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);        // Subchunk1Size (16 for PCM)
    view.setUint16(20, 1, true);         // AudioFormat (1 for PCM)
    view.setUint16(22, 1, true);         // NumChannels (1 = Mono)
    view.setUint32(24, targetRate, true);// SampleRate (16000)
    view.setUint32(28, targetRate * 2, true); // ByteRate (16000 * 1 * 16/8)
    view.setUint16(32, 2, true);         // BlockAlign (1 * 16/8)
    view.setUint16(34, 16, true);        // BitsPerSample (16-bit)

    // data Chunk
    writeString(view, 36, 'data');
    view.setUint32(40, resampled.length * 2, true);

    // Convert Float32 to 16-bit PCM integer
    let pcmOffset = 44;
    for (let i = 0; i < resampled.length; i++) {
        let s = Math.max(-1, Math.min(1, resampled[i]));
        view.setInt16(pcmOffset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
        pcmOffset += 2;
    }

    return new Blob([view], { type: 'audio/wav' });
}

function writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
    }
}

// Collapsible JSON viewer
document.getElementById('toggleJsonBtn').addEventListener('click', () => {
    const viewer = document.getElementById('rawJsonViewer');
    const icon = document.querySelector('.collapse-icon');
    if (viewer.style.display === 'none') {
        viewer.style.display = 'block';
        icon.textContent = '▼';
    } else {
        viewer.style.display = 'none';
        icon.textContent = '▶';
    }
});
