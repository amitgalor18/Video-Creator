import subprocess
from pathlib import Path
# from main import generate_video   # adjust import to where the function lives

captions = [
    "איפה אתה רוצה להיות?",
    "למד משהו חדש היום.",
    "הצלחות קטנות מובילות גדולות.",
    "תפרו את הדרך שלך.",
    "העתיד נמצא בידיים שלך."
]

def ffprobe_duration(path: Path) -> float:
    """Return the duration of an audio file in seconds via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ]
    out = subprocess.check_output(cmd).decode().strip()
    return float(out)

def generate_video(captions, buffer_sec: int = 1):
    """
    Build videos/output_video.mp4 where:
    • image_i.webp is on screen for (voice_i.mp3 length + buffer_sec)
    • the buffer is silence over the same still frame
    """
    img_dir = Path("images")
    aud_dir = Path("voiceovers")
    vid_dir = Path("videos")
    tmp_dir = Path("tmp_segments")
    
    vid_dir.mkdir(exist_ok=True)
    tmp_dir.mkdir(exist_ok=True)
    
    images = [img_dir / f"image_{i}.webp" for i in range(1, len(captions)+1)]
    voiceovers = [aud_dir / f"voiceover_{i}.mp3" for i in range(1, len(captions)+1)]
    
    segments = []
    
    # 1️⃣ build (image + audio + silence) segment_i.mp4
    for i, (img, mp3) in enumerate(zip(images, voiceovers), 1):
        seg = tmp_dir / f"segment_{i}.mp4"
        
        # Get the exact duration of the voiceover
        voice_duration = ffprobe_duration(mp3)
        total_duration = voice_duration + buffer_sec
        
        # Create segment with exact timing control
        # First create a silent audio track for the buffer
        silent_audio = tmp_dir / f"silent_{i}.wav"
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"anullsrc=channel_layout=mono:sample_rate=48000",
            "-t", str(buffer_sec),
            "-c:a", "pcm_s16le",
            str(silent_audio)
        ], check=True)
        
        # Concatenate the original audio with the silent buffer
        buffered_audio = tmp_dir / f"buffered_{i}.wav"
        audio_concat_list = tmp_dir / f"audio_concat_{i}.txt"
        with audio_concat_list.open("w") as f:
            # Use absolute paths to avoid path resolution issues
            f.write(f"file '{mp3.absolute().as_posix()}'\n")
            f.write(f"file '{silent_audio.absolute().as_posix()}'\n")
        
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(audio_concat_list),
            "-c:a", "pcm_s16le",
            str(buffered_audio)
        ], check=True)
        
        # Now create the video segment with the buffered audio
        subprocess.run([
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(img),
            "-i", str(buffered_audio),
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-tune", "stillimage",
            "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-t", str(total_duration),
            str(seg)
        ], check=True)
        
        segments.append(seg)
        print(f"✅ Created segment {i}: {total_duration:.2f}s (voice: {voice_duration:.2f}s + buffer: {buffer_sec}s)")
    
    # 2️⃣ concat all segments *without re-encoding*
    concat_list = tmp_dir / "concat.txt"
    with concat_list.open("w") as f:
        for seg in segments:
            f.write(f"file '{seg.absolute().as_posix()}'\n")
    
    out_video = vid_dir / "output_video.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy", str(out_video)
    ], check=True)
    
    print(f"✅ Video generated successfully: {out_video}")
    
    # Calculate and display total video duration
    total_duration = sum(ffprobe_duration(aud) + buffer_sec for aud in voiceovers)
    print(f"📊 Total video duration: {total_duration:.2f}s")


generate_video(captions) 