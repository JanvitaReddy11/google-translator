# Healthcare Translation App - User Guide

## Introduction
The Healthcare Translation App is designed to break down language barriers in healthcare settings. This guide will help you use the application to record speech, translate it, and play back the translation in the patient's language.


## Getting Started

### System Requirements
- Modern web browser (Chrome, Firefox, Edge recommended)
- Microphone access
- Speakers or headphones for audio playback
- Internet connection

### Accessing the Application
1. Open your terminal
2. Install the requirements "pip install requirements.txt"
3. In the root folder enter the command " uvicorn main:app --reload"
4. Navigate to the frontend folder name and enter the command "python -m http.server 8001"
5. Navigate to the Healthcare Translation App URL
6. Allow microphone access when prompted

## Basic Features

### Language Selection
1. Locate the language dropdown at the top of the app
2. Click to open the dropdown menu
3. Select the target language for translation

**Available languages include:**
- English (US)
- Hindi
- Spanish
- French
- German
- Chinese (Mandarin)
- Japanese
- Russian
- Italian
- Portuguese (Brazil)


### Recording Speech
1. Select your desired target language
2. Click the "Start Recording" button
3. Begin speaking clearly at a moderate pace
4. The translation will appear simultaneously in the "Translated Text" section
6. Click "Stop Recording" when finished speaking



### Audio Playback
1. After recording and translation is complete
2. Click the "Convert to Speech" button
3. The translated text will be converted to spoken audio
4. Audio will play automatically through your speakers
5. If audio doesn't play automatically, click the play button on the audio player


### Managing Sessions
1. To start a new translation session, click the "Clear Session" button
2. This will reset all text fields and audio
3. The application will be ready for a new recording

