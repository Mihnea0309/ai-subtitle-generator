# AI Desktop Subtitle Generator

A local desktop application built with **Python** and **PyQt5** that automatically transcribes audio from video files into synchronized `.srt` subtitles using **OpenAI's Whisper**, featuring multi-language translation and an integrated **VLC media player** for instant playback[cite: 10, 11, 12].

## Key Features
- **Local Speech-to-Text Transcription:** Uses OpenAI Whisper models (`base`, `small`, `medium`, `large`, plus English-optimized `.en` variants) to generate UTF-8 encoded `.srt` subtitle files locally without watermarks or usage limits[cite: 11, 15, 16].
- **Hardware Acceleration (CPU / GPU):** Automatically detects CUDA-compatible GPUs via **PyTorch**, allowing users to switch between CPU and GPU processing depending on available hardware resources[cite: 12, 15, 16].
- **Multi-Language Translation:** Translates generated subtitles into multiple languages (English, Romanian, French, Spanish, German, Italian) using Google Translate integration[cite: 12, 14].
- **Integrated Media Player:** Built-in VLC player instance that automatically loads the video alongside the newly generated `.srt` file with timeline scrubbing controls[cite: 12, 14].

## Tech Stack
- **Language:** Python 3[cite: 11]
- **GUI Framework:** PyQt5[cite: 11, 12]
- **AI / ML Engine:** OpenAI Whisper, PyTorch (`torch`)[cite: 11, 12]
- **Media & Translation:** `python-vlc`, Google Translate API[cite: 12]

## Screenshots
[Main Interface](screenshots/main_ui.png)
[Video Playback](screenshots/player_ui.png)


## Installation & Setup

1. **Prerequisites:**
   - Python 3.8+
   - [VLC Media Player](https://www.videolan.org/) installed on your system (required for the embedded player)[cite: 12]
   - `ffmpeg` installed and added to system PATH

2. **Clone the repository:**
   ```bash
   git clone [https://github.com/Mihnea0309/whisper-subtitle-generator.git](https://github.com/Mihnea0309/whisper-subtitle-generator.git)
   cd whisper-subtitle-generator
