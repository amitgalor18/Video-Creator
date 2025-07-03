# AutoGen Hebrew "Movie-Producer" Demo

A minimal multi-agent **AutoGen** workflow that writes a Hebrew script, generates voice-overs using DeepDub & StableDiffusion images, and stitches them into a perfectly-synced short video.

> ✨ The pipeline is entirely local – it talks to your own vLLM-hosted model, DeepDub, Stability AI, and FFmpeg. To make it entirely on-prem it's possible to delegate the voiceover and image generations to open source models as well.

---

## 📂 Project layout

```
video-creator/
├─ images/           # generated .webp frames (graphic_designer)
├─ voiceovers/       # generated .mp3 files (voice_actor)
├─ videos/           # final videos land here (director)
├─ tmp_segments/     # temp clips used by director (auto-clean if git-ignored)
├─ main.py           # interactive AutoGen demo
├─ test_director.py  # run generate_video() directly – no AutoGen needed
├─ video_utils.py    # generate_video() and helpers (imported by main)
├─ requirements.txt
├─ .env              # your API keys (not tracked!)
└─ README.md         # you are here
```

---

## 🚀 Quick start

```bash
# 1. clone & enter the repo
git clone https://github.com/<your-username>/video-creator.git
cd video-creator

# 2. create virtualenv
python -m venv venv
source venv/bin/activate

# 3. install deps
pip install -r requirements.txt

# 4. add secrets
touch .env  # then edit .env and add:
# OPENAI_API_KEY=...
# DEEPDUB_API_KEY=...
# STABILITY_API_KEY=...

# 5. run the full multi-agent demo
python main.py
```

Inside the console, enter a topic in Hebrew (e.g. `התפתחות בקריירה והתקדמות מקצועית`).
The agents will:

1. **script\_writer** – craft 5 Hebrew captions.
2. **voice\_actor** – generate 5 MP3 voice-overs.
3. **graphic\_designer** – translate captions → English prompts → 5 abstract images.
4. **director** – call `generate_video()` to create `videos/output_video.mp4`.

---

## 🎬 Testing only the Director

If you already have `images/` & `voiceovers/` populated, skip the other agents:

```bash
python test_director.py        # one-liner test
```

---

## 🔨 generate\_video() internals

`video_utils.generate_video(captions: list[str], buffer_sec: int = 1)`

* For each image-audio pair it:

  1. pads the MP3 with **buffer\_sec** of silence (FFmpeg `apad+atrim`).
  2. loops the still image for the exact new duration.
  3. saves a self-contained `segment_i.mp4`.
* When all segments are ready it concatenates them **losslessly** with FFmpeg `concat`.

---

## 🗝️ Environment variables

| Variable            | Purpose                                         |
| ------------------- | ----------------------------------------------- |
| `OPENAI_API_KEY`    | any string – passed to your local vLLM endpoint |
| `DEEPDUB_API_KEY`   | DeepDub TTS                                     |
| `STABILITY_API_KEY` | Stability AI image generation                   |

Put them in `.env` (automatically loaded by `dotenv`).

---

## 🛠️ Development tips

* Install a newer FFmpeg (≥ 4.3) if you want the `tpad` filter instead of the compatibility patch.
* To tweak caption length or styles, edit the agent **system messages** in `main.py`.
* Add `tmp_segments/` and `videos/` to your `.gitignore` – they can be regenerated.

---

## 📝 License

MIT — do whatever you want, no warranty.
