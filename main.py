import os
from dotenv import load_dotenv
from autogen_agentchat.agents import AssistantAgent
import requests
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.conditions import TextMentionTermination
import asyncio
import subprocess
from pathlib import Path
import shlex
# from translate import Translator



load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")
deepdub_api_key = os.getenv("DEEPDUB_API_KEY")
stability_api_key = os.getenv("STABILITY_API_KEY")

try:
    from deepdub import DeepdubClient
except ImportError:
    import pip
    pip.main(['install', 'deepdub'])
    from deepdub import DeepdubClient

dd = DeepdubClient(api_key="dd-c3pLZxfSaYaOUlQAHjpzfxO9E6Te4b6J8ddc1719")


def generate_voiceovers(messages: list[str]) -> list[str]:
    """
    Generate voiceovers for a list of messages using Deepdub API.
    
    Args:
        messages: List of messages to convert to speech
        
    Returns:
        List of file paths to the generated audio files
    """
    os.makedirs("voiceovers", exist_ok=True)
    
    # Check for existing files first
    audio_file_paths = []
    for i in range(1, len(messages) + 1):
        file_path = f"voiceovers/voiceover_{i}.mp3"
        if os.path.exists(file_path):
            audio_file_paths.append(file_path)
            
    # If all files exist, return them
    if len(audio_file_paths) == len(messages):
        print("All voiceover files already exist. Skipping generation.")
        return audio_file_paths
        
    # Generate missing files one by one 9fe62200-5715-430f-9bbc-e9aa4c14aa1c_reading-neutral
    audio_file_paths = []
    for i, message in enumerate(messages, 1):
        try:
            save_file_path = f"voiceovers/voiceover_{i}.mp3"
            if os.path.exists(save_file_path):
                print(f"File {save_file_path} already exists, skipping generation.")
                audio_file_paths.append(save_file_path)
                continue

            print(f"Generating voiceover {i}/{len(messages)}...")
            
            # Generate audio with ElevenLabs
            audio_out = dd.tts(
                text=message, 
                voice_prompt_id="80e0796e-d509-489c-90ff-06e2e32dbe16_reading-neutral", 
                model="dd-etts-2.5", 
                locale="he-IL", 
            )
            
            # # Collect audio chunks
            # audio_chunks = []
            # for chunk in response:
            #     if chunk:
            #         audio_chunks.append(chunk)
            
            # Save to file
            # with open(save_file_path, "wb") as f:
            #     for chunk in audio_chunks:
            #         f.write(chunk)
            with open(save_file_path, "wb") as f:
                f.write(audio_out)
                        
            print(f"Voiceover {i} generated successfully")
            audio_file_paths.append(save_file_path)
        
        except Exception as e:
            print(f"Error generating voiceover for message: {message}. Error: {e}")
            continue
            
    return audio_file_paths

def generate_images(prompts: list[str]):
    """
    Generate images based on text prompts using Stability AI API.
    
    Args:
        prompts: List of text prompts to generate images from
    """
    seed = 42
    output_dir = "images"
    os.makedirs(output_dir, exist_ok=True)

    # API config
    stability_api_url = "https://api.stability.ai/v2beta/stable-image/generate/core"
    headers = {
        "Authorization": f"Bearer {stability_api_key}",
        "Accept": "image/*"
    }

    for i, prompt in enumerate(prompts, 1):
        print(f"Generating image {i}/{len(prompts)} for prompt: {prompt}")

        # Skip if image already exists
        image_path = os.path.join(output_dir, f"image_{i}.webp")
        if not os.path.exists(image_path):
            # Prepare request payload
            payload = {
                "prompt": (None, prompt),
                "output_format": (None, "webp"),
                "height": (None, "512"),
                "width": (None, "512"),
                "seed": (None, str(seed))
            }

            try:
                response = requests.post(stability_api_url, headers=headers, files=payload)
                if response.status_code == 200:
                    with open(image_path, "wb") as image_file:
                        image_file.write(response.content)
                    print(f"Image saved to {image_path}")
                else:
                    print(f"Error generating image {i}: {response.json()}")
            except Exception as e:
                print(f"Error generating image {i}: {e}")

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

def generate_video(captions: list[str], buffer_sec: int = 1):
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
            f.write(f"file '{mp3.as_posix()}'\n")
            f.write(f"file '{silent_audio.as_posix()}'\n")
        
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
            f.write(f"file '{seg.as_posix()}'\n")
    
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


script_writer = AssistantAgent(
    name="script_writer",
    model_client=OpenAIChatCompletionClient(
        model="google/gemma-3-4b",
        api_key="placeholder",
        base_url="http://127.0.0.1:1234/v1",
        model_info={
            "function_calling": True,
            "json_output": True,
            "vision": False,
            "family": "unknown"
        }
    ),
    system_message='''
        You are a creative assistant tasked with writing a script for a short video. 
        The script should consist of captions designed to be displayed on-screen, with the following guidelines:
            1.	The captions must be in Hebrew.
            2.  Each caption must be short and impactful (no more than 8 words) to avoid overwhelming the viewer.
            3.	The script should have exactly 5 captions, each representing a key moment in the story.
            4.	The flow of captions must feel natural, like a compelling voiceover guiding the viewer through the narrative.
            5.	Always start with a question or a statement that keeps the viewer wanting to know more.
            6.  You must also include the topic and takeaway in your response.
            7.  The caption values must ONLY include the captions, no additional meta data or information.

            Output your response in the following JSON format:
            {
                "topic": "topic",
                "takeaway": "takeaway",
                "captions": [
                    "caption1",
                    "caption2",
                    "caption3",
                    "caption4",
                    "caption5"
                ]
            }
    '''
)

voice_actor = AssistantAgent(
    name="voice_actor",
    model_client=OpenAIChatCompletionClient(
        model="google/gemma-3-4b",
        api_key="placeholder",
        base_url="http://127.0.0.1:1234/v1",
        model_info={
            "function_calling": True,
            "json_output": True,
            "vision": False,
            "family": "unknown"
        }
    ),
    tools=[generate_voiceovers],
    system_message='''
        You are a helpful agent tasked with generating and saving voiceovers.
        Only respond with 'TERMINATE' once files are successfully saved locally.
    '''
)


graphic_designer = AssistantAgent(
    name="graphic_designer",
    model_client=OpenAIChatCompletionClient(
        model="google/gemma-3-4b",
        api_key="placeholder",
        base_url="http://127.0.0.1:1234/v1",
        model_info={
            "function_calling": True,
            "json_output": True,
            "vision": False,
            "family": "unknown"
        }
    ),
    tools=[generate_images],
    system_message='''
        You are a helpful agent tasked with generating and saving images for a short video.
        **All prompts you pass to the image generator must be in English** because the API only supports English input.
        You are given a list of captions (in Hebrew).
        You will convert each caption into an optimized English prompt for the image generation tool.
        The prompts should be descriptive, not only writing the caption but describing the required image in detail.
        Your prompts must be concise and maintain the same style and tone as the captions while ensuring continuity between the images.
        Your prompts must mention that the output images MUST be in: "Abstract Art Style / Ultra High Quality." (Include with each prompt)
        You will then use the prompts list to generate images for each provided caption.
        Only respond with 'TERMINATE' once the files are successfully saved locally.
    '''
)

director = AssistantAgent(
    name="director",
    model_client=OpenAIChatCompletionClient(
        model="google/gemma-3-4b",
        api_key="placeholder",
        base_url="http://127.0.0.1:1234/v1",
        model_info={
            "function_calling": True,
            "json_output": True,
            "vision": False,
            "family": "unknown"
        }
    ),
    tools=[generate_video],
    system_message='''
        You are a helpful agent tasked with generating the final video.
        Steps:
        1. Build a 5-image slideshow (5 s per slide) from the files the graphic designer saved.
        2. Concatenate the 5 MP3 voice-overs in order.
        3. Mux the slideshow + audio into videos/output_video.mp4.
        Respond with "TERMINATE" once done.
            '''
        )

# Set up termination condition
termination = TextMentionTermination("TERMINATE")

# Create the AutoGen team
agent_team = RoundRobinGroupChat(
    [script_writer, voice_actor, graphic_designer, director],
    termination_condition=termination,
    max_turns=4
)


# Interactive console loop
async def main():
    while True:
        user_input = input("Enter a message (type 'exit' to leave): ")
        if user_input.strip().lower() == "exit":
            break
        
        # Run the team with the user input and display results
        stream = agent_team.run_stream(task=user_input)
        await Console(stream)

if __name__ == "__main__":
    asyncio.run(main())