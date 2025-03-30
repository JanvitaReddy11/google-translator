// 

// Modified version of app.js to store complete conversations with file saving functionality
// Improved stop conditions and connection handling

let transcribedSegments = []; // Array to store all transcribed segments
let translatedSegments = []; // Array to store all translated segments
let socket; // WebSocket variable
let mediaRecorder; // MediaRecorder variable
let mediaStream; // MediaStream variable
let isRecording = false;
let sessionStartTime; // To track when recording session started
let savedFilePath = null; // Track the saved file path
let stopCommandSent = false; // Flag to track if stop command was sent

document.getElementById("record-btn").addEventListener("click", function () {
    console.log("Record button clicked.");
    if (!isRecording) {
        startRecordingAndTranscribing();
    } else {
        stopRecording();
    }
});

async function startRecordingAndTranscribing() {
    const statusText = document.getElementById("status");
    statusText.innerText = "Starting recording...";
    console.log("Starting recording...");

    try {
        // Clear previous transcriptions and audio
        clearSession();
        
        // Reset stop command flag
        stopCommandSent = false;
        
        // Set session start time
        sessionStartTime = new Date();
        
        // Close existing WebSocket connection if open
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.close();
        }

        // Stop and clean up any existing media stream
        if (mediaStream) {
            mediaStream.getTracks().forEach(track => track.stop());
        }

        // Get the selected language for translation
        const selectedLanguage = document.getElementById("language-select").value;
        
        // Disable TTS button until we have a translation
        document.getElementById("audio-btn").disabled = true;
        
        // Establish WebSocket connection - Add language parameter
        const wsUrl = `ws://127.0.0.1:8000/record_and_transcribe?language=${selectedLanguage}`;
        socket = new WebSocket(wsUrl);
        console.log(`Creating WebSocket connection to ${wsUrl}...`);

        socket.onopen = async () => {
            console.log("WebSocket connected successfully. State:", socket.readyState);
            statusText.innerText = "Connected ✓ Starting microphone...";

            try {
                // Get access to the microphone
                mediaStream = await navigator.mediaDevices.getUserMedia({ 
                    audio: {
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true,
                        sampleRate: 16000
                    } 
                });

                // Create a new MediaRecorder instance
                const options = { mimeType: 'audio/webm' }; // Simplified MIME type
                mediaRecorder = new MediaRecorder(mediaStream, options);
                
                console.log("MediaRecorder created with options:", options);
                console.log("MediaRecorder state:", mediaRecorder.state);
                
                // Handle data available event
                mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0 && socket && socket.readyState === WebSocket.OPEN) {
                        console.log(`Sending audio chunk: ${event.data.size} bytes`);
                        socket.send(event.data);
                    }
                };

                // Handle recording stopped event
                mediaRecorder.onstop = () => {
                    console.log("MediaRecorder stopped.");
                    statusText.innerText = "Recording stopped. Processing final transcript...";
                    
                    // Stop audio stream
                    if (mediaStream) {
                        mediaStream.getTracks().forEach(track => track.stop());
                    }

                    // Send a stop command to the server if not already sent
                    sendStopCommand();
                    
                    // Set a definite timeline for cleanup
                    setTimeout(() => {
                        closeSocketConnection();
                        // Enable the audio button after recording is stopped
                        document.getElementById("audio-btn").disabled = false;
                        document.getElementById("clear-btn").disabled = false;
                    }, 3000);
                };

                // Start recording with small chunks for real-time processing
                mediaRecorder.start(250); 
                isRecording = true;
                
                // Update UI
                document.getElementById("record-btn").innerText = "Stop Recording";
                statusText.innerText = "Recording in progress...";
                console.log("Recording started successfully.");

            } catch (mediaError) {
                console.error("Error accessing microphone:", mediaError);
                statusText.innerText = "Error accessing microphone: " + mediaError.message;
                if (socket && socket.readyState === WebSocket.OPEN) {
                    socket.close();
                }
            }
        };

        socket.onmessage = async (event) => {
            console.log("Received message from server:", event.data);
            try {
                const data = JSON.parse(event.data);
                
                // If we got a connection confirmation
                if (data.status === "connected") {
                    console.log("Connection confirmed with ID:", data.connection_id);
                }
                
                // Process real-time original transcription
                // if (data.original) {
                //     // Handle UI updates - show latest in text area
                //     document.getElementById("transcribed-text").innerText = data.original;
                    
                //     // Only store final transcriptions to avoid duplicates
                //     if (data.is_final) {
                //         transcribedSegments.push({
                //             text: data.original,
                //             isFinal: true
                //         });
                        
                //         console.log("Added transcribed segment:", transcribedSegments[transcribedSegments.length-1]);
                //     }
                    
                //     // Show status
                //     if (data.is_final) {
                //         statusText.innerText = "Final transcription received";
                //     } else {
                //         statusText.innerText = "Transcribing...";
                //     }
                // }
                
                // Process translated text if available
                if (data.translation) {
                    // Handle UI updates - show latest in text area
                    document.getElementById("translated-text").innerText = data.translation;
                    
                    // Only store final translations to avoid duplicates
                    if (data.is_final) {
                        translatedSegments.push({
                            text: data.translation,
                            isFinal: true
                        });
                        
                        console.log("Added translated segment:", translatedSegments[translatedSegments.length-1]);
                    }
                }
                
                // Handle error messages
                if (data.error) {
                    console.error("Server error:", data.error);
                    statusText.innerText = "Server error: " + data.error;
                }
                
                // Handle COMPLETE status from server - indicates server is done processing
                if (data.status === "COMPLETE") {
                    console.log("Received COMPLETE status from server");
                    statusText.innerText = "Processing complete";
                    
                    // Close socket after ensuring all data is received
                    setTimeout(() => {
                        closeSocketConnection();
                        document.getElementById("audio-btn").disabled = false;
                        document.getElementById("clear-btn").disabled = false;
                    }, 1000);
                }
            } catch (parseError) {
                console.error("Error parsing WebSocket message:", parseError);
                console.error("Raw message:", event.data);
                statusText.innerText = "Error parsing server message";
            }
        };

        socket.onclose = (event) => {
            console.log("WebSocket closed. Code:", event.code, "Reason:", event.reason, "Clean:", event.wasClean);
            statusText.innerText = `Connection closed. Code: ${event.code}`;
            resetRecordButton();
            
            // Enable the audio button after connection is closed if we have content
            if (translatedSegments.length > 0 || transcribedSegments.length > 0) {
                document.getElementById("audio-btn").disabled = false;
                document.getElementById("clear-btn").disabled = false;
            }
        };

        socket.onerror = (error) => {
            console.error("WebSocket error:", error);
            statusText.innerText = "Connection error";
            resetRecordButton();
        };

    } catch (error) {
        console.error("Error during recording setup:", error);
        statusText.innerText = "Setup error: " + error.message;
        resetRecordButton();
    }
}

// New helper function to send stop command
function sendStopCommand() {
    if (stopCommandSent) {
        console.log("Stop command already sent, skipping");
        return;
    }
    
    if (socket && socket.readyState === WebSocket.OPEN) {
        try {
            console.log("Sending stop command to server...");
            socket.send(JSON.stringify({ command: "stop" }));
            stopCommandSent = true;
        } catch (e) {
            console.error("Error sending stop command:", e);
        }
    } else {
        console.log("WebSocket not open, cannot send stop command");
    }
}

// New helper function to close socket connection
function closeSocketConnection() {
    if (socket) {
        if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
            console.log("Closing WebSocket connection");
            socket.close(1000, "User stopped recording - normal closure");
        } else {
            console.log("WebSocket already closing or closed. State:", socket.readyState);
        }
    }
}

function stopRecording() {
    console.log("Stopping recording...");
    const statusText = document.getElementById("status");
    statusText.innerText = "Stopping recording...";
    
    isRecording = false;
    
    // First send the stop command regardless of mediaRecorder state
    sendStopCommand();
    
    // Then stop the mediaRecorder if active
    if (mediaRecorder && mediaRecorder.state === "recording") {
        try {
            console.log("Stopping mediaRecorder");
            mediaRecorder.stop();
        } catch (error) {
            console.error("Error stopping mediaRecorder:", error);
        }
    } else {
        console.log("MediaRecorder not in recording state, cannot stop");
        
        // If mediaRecorder isn't active, we need to handle cleanup here
        if (mediaStream) {
            console.log("Stopping media stream tracks");
            mediaStream.getTracks().forEach(track => track.stop());
        }
        
        // Set a timeout to ensure the stop command is processed by the server
        setTimeout(() => {
            closeSocketConnection();
            // Enable the audio button after recording is stopped
            document.getElementById("audio-btn").disabled = false;
            document.getElementById("clear-btn").disabled = false;
        }, 2000);
    }
    
    // Update UI
    resetRecordButton();
}

function resetRecordButton() {
    isRecording = false;
    document.getElementById("record-btn").innerText = "Start Recording";
}

console.log("Attempting to free port 8000 before sending TTS request...");

async function killProcessOnPort() {
    try {
        const killResponse = await fetch("http://127.0.0.1:8000/api/kill_port/", { method: "POST" });
        const killData = await killResponse.json();
        console.log("Kill process response:", killData.message);
    } catch (error) {
        console.error("Error killing process:", error);
    }
}


async function convertTextToSpeech() {
    const statusText = document.getElementById("status");
    statusText.innerText = "Converting to speech...";

    // Get the translated content directly
    let translatedContent = translatedSegments.map(s => s.text).join(" ").trim();
    let originalContent = transcribedSegments.map(s => s.text).join(" ").trim();
    
    // Use original content as fallback if no translation available
    let contentToSend = translatedContent || originalContent;
    
    if (!contentToSend) {
        console.log("No content to send to TTS");
        statusText.innerText = "No content to convert to speech";
        return;
    }

    const selectedLanguage = document.getElementById("language-select").value;
    
    // Send the text directly to the TTS endpoint
    const dataToSend = {
        text: contentToSend,
        language_code: selectedLanguage
    };

    console.log("Starting direct TTS with text content", dataToSend);

    try {
        console.log("Sending TTS request...");

        await killProcessOnPort(); 
        const response = await fetch("http://127.0.0.1:8000/api/tts/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(dataToSend),
        });

        console.log("TTS response received. Status:", response.status);

        if (!response.ok) {
            const errorText = await response.text();
            console.error("TTS error response:", errorText);
            throw new Error(`HTTP error! Status: ${response.status}. Details: ${errorText}`);
        }

        const data = await response.json();
        console.log("TTS Response Data:", data);

        if (data.audio_url) {
            console.log("Playing audio:", data.audio_url);
            statusText.innerText = "Playing audio...";

            const audio = document.getElementById("audio-output");
            
            // Make sure audio element is visible before playing
            audio.style.display = "block"; 
            
            // Set the source with a cache-busting parameter to avoid browser caching
            audio.src = 'http://127.0.0.1:8000' + data.audio_url;
            
            // Force audio to load
            audio.load();
            
            // Try to play the audio automatically
            audio.play().then(() => {
                console.log("Audio is playing automatically");
                statusText.innerText = "Audio playing";
                
                // Add event listener for when audio finishes playing
                audio.onended = function() {
                    statusText.innerText = "Session complete. Ready for next recording.";
                };
            }).catch((error) => {
                console.error("Error playing audio:", error);
                statusText.innerText = "Error playing audio: " + error.message;
                
                // If autoplay fails, show a message to the user
                alert("Autoplay was blocked. Please click the play button to hear the audio.");
            });
        } else {
            console.log("No audio file received.");
            statusText.innerText = "No audio file received.";
        }
    } catch (error) {
        console.error("Error during TTS conversion:", error);
        statusText.innerText = "TTS error: " + error.message;
    }
}

document.getElementById("audio-btn").addEventListener("click", function () {
    console.log("Audio button clicked.");
    convertTextToSpeech();
});

// Add clear button functionality
document.getElementById("clear-btn").addEventListener("click", function() {
    clearSession();
    document.getElementById("status").innerText = "Ready to record";
});

// Function to clear the session
function clearSession() {
    // Clear text displays
    //
    //document.getElementById("transcribed-text").innerText = "";
    document.getElementById("translated-text").innerText = "";
    
    // Reset stored values
    transcribedSegments = [];
    translatedSegments = [];
    sessionStartTime = null;
    savedFilePath = null;
    stopCommandSent = false;
    
    // Hide audio player
    const audio = document.getElementById("audio-output");
    audio.pause();
    audio.src = "";
    audio.style.display = "none";
    
    // Disable buttons
    document.getElementById("audio-btn").disabled = true;
    document.getElementById("clear-btn").disabled = true;
    
    console.log("Session cleared");
}