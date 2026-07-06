"""
The Health Desk — YouTube Shorts Automation
Free stack: edge-tts + Pexels + moviepy + Pillow + Whisper + YouTube API
"""
import os, json, asyncio, subprocess, textwrap, requests
from faster_whisper import WhisperModel
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import edge_tts
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.VideoClip import ImageClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.fx.resize import resize
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.tools.subtitles import SubtitlesClip
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ── Config ─────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent.parent
OUTPUT_DIR  = BASE_DIR / "output"
ASSETS_DIR  = BASE_DIR / "assets"
OUTPUT_DIR.mkdir(exist_ok=True)

PEXELS_KEY  = os.environ["PEXELS_API_KEY"]
YT_CREDS    = {
    "client_id":     os.environ["YT_CLIENT_ID"],
    "client_secret": os.environ["YT_CLIENT_SECRET"],
    "refresh_token": os.environ["YT_REFRESH_TOKEN"],
    "token_uri":     "https://oauth2.googleapis.com/token",
}

BRAND_GREEN = (22, 179, 100)
BRAND_DARK  = (15, 15, 20)
WHITE       = (255, 255, 255)

VIDEO_W, VIDEO_H = 1080, 1920   # 9:16


# ── 1. Voiceover via edge-tts ──────────────────────────────────────────────────
async def generate_voiceover(text: str, out_path: Path):
    communicate = edge_tts.Communicate(
        text,
        voice="en-US-GuyNeural",   # mature male voice, perfect for 45+ health
        rate="+5%",
        volume="+10%",
    )
    await communicate.save(str(out_path))
    print(f"  ✓ Voiceover: {out_path.name}")


# ── 2. Stock footage via Pexels ────────────────────────────────────────────────
def download_pexels_video(query: str, out_path: Path, min_duration: int = 55) -> bool:
    headers = {"Authorization": PEXELS_KEY}
    r = requests.get(
        "https://api.pexels.com/videos/search",
        headers=headers,
        params={"query": query, "per_page": 10, "orientation": "portrait"},
    )
    videos = r.json().get("videos", [])
    for v in videos:
        for f in v.get("video_files", []):
            if f.get("width") == 1080 and f.get("height") == 1920 and v.get("duration", 0) >= min_duration:
                data = requests.get(f["link"]).content
                out_path.write_bytes(data)
                print(f"  ✓ Stock footage: {out_path.name}")
                return True
    # fallback: any portrait video
    for v in videos:
        for f in v.get("video_files", []):
            if f.get("height", 0) > f.get("width", 1):
                data = requests.get(f["link"]).content
                out_path.write_bytes(data)
                print(f"  ✓ Stock footage (fallback): {out_path.name}")
                return True
    return False


# ── 3. Thumbnail via Pillow ────────────────────────────────────────────────────
def generate_thumbnail(headline: str, product: str, out_path: Path):
    img = Image.new("RGB", (1280, 720), BRAND_DARK)
    draw = ImageDraw.Draw(img)

    # green accent bar left
    draw.rectangle([0, 0, 12, 720], fill=BRAND_GREEN)

    # brand strip top-right
    draw.rectangle([900, 0, 1280, 60], fill=BRAND_GREEN)
    try:
        font_sm = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 26)
        font_lg = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 68)
        font_md = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 34)
    except OSError:
        font_sm = font_lg = font_md = ImageFont.load_default()

    draw.text((910, 12), "THE HEALTH DESK", font=font_sm, fill=WHITE)

    # product badge
    badge_text = product.upper()
    draw.rounded_rectangle([60, 80, 60 + len(badge_text) * 22 + 30, 140], radius=8, fill=BRAND_GREEN)
    draw.text((75, 88), badge_text, font=font_sm, fill=WHITE)

    # headline (word-wrapped)
    wrapped = textwrap.wrap(headline, width=28)
    y = 170
    for line in wrapped[:3]:
        draw.text((60, y), line, font=font_lg, fill=WHITE)
        y += 80

    # "HONEST REVIEW" badge bottom-left
    draw.rounded_rectangle([60, 620, 340, 680], radius=6, fill=(40, 40, 50))
    draw.text((75, 630), "HONEST REVIEW  •  45+", font=font_md, fill=BRAND_GREEN)

    img.save(str(out_path), quality=95)
    print(f"  ✓ Thumbnail: {out_path.name}")


# ── 4. Auto-captions via Whisper ───────────────────────────────────────────────
def generate_srt(audio_path: Path, srt_path: Path):
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(audio_path))
    lines = []
    idx = 1
    for seg in segments:
        start = _fmt_time(seg.start)
        end   = _fmt_time(seg.end)
        text  = seg.text.strip()
        lines.append(f"{idx}\n{start} --> {end}\n{text}\n")
        idx += 1
    srt_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  ✓ Captions SRT: {srt_path.name}")


def _fmt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ── 5. Assemble final video ────────────────────────────────────────────────────
def assemble_video(video_path: Path, audio_path: Path, srt_path: Path, out_path: Path):
    video = VideoFileClip(str(video_path))
    audio = AudioFileClip(str(audio_path))
    duration = audio.duration

    # trim/loop video to match audio duration
    if video.duration < duration:
        loops = int(duration / video.duration) + 1
        from moviepy.video.fx.loop import loop
        video = loop(video, n=loops)
    video = video.subclip(0, duration)

    # resize to 9:16 if needed
    if video.w != VIDEO_W or video.h != VIDEO_H:
        video = resize(video, height=VIDEO_H)
        if video.w > VIDEO_W:
            x1 = (video.w - VIDEO_W) // 2
            video = video.crop(x1=x1, x2=x1 + VIDEO_W)

    # dim background
    from moviepy.video.fx.colorx import colorx
    video = colorx(video, 0.55)

    # add branded overlay (top bar)
    overlay = Image.new("RGBA", (VIDEO_W, 90), (*BRAND_GREEN, 230))
    overlay_clip = ImageClip(overlay).set_duration(duration).set_position(("center", 0))

    # burn captions
    try:
        generator = lambda txt: _caption_clip(txt)
        subtitles = SubtitlesClip(str(srt_path), generator)
        final = CompositeVideoClip([video, overlay_clip, subtitles.set_position(("center", 0.78), relative=True)])
    except Exception:
        final = CompositeVideoClip([video, overlay_clip])

    final = final.set_audio(audio)
    final.write_videofile(
        str(out_path),
        fps=30,
        codec="libx264",
        audio_codec="aac",
        ffmpeg_params=["-pix_fmt", "yuv420p", "-profile:v", "baseline", "-level", "3.1"],
        logger=None,
    )
    print(f"  ✓ Video: {out_path.name}")


def _caption_clip(txt: str):
    from PIL import Image as PILImage, ImageDraw as PILDraw, ImageFont as PILFont
    try:
        fnt = PILFont.truetype("C:/Windows/Fonts/arialbd.ttf", 52)
    except OSError:
        fnt = PILFont.load_default()
    wrapped = textwrap.wrap(txt, width=22)
    img = PILImage.new("RGBA", (VIDEO_W, 180), (0, 0, 0, 0))
    d = PILDraw.Draw(img)
    y = 0
    for line in wrapped[:3]:
        bbox = d.textbbox((0, 0), line, font=fnt)
        w = bbox[2] - bbox[0]
        x = (VIDEO_W - w) // 2
        # shadow
        d.text((x + 2, y + 2), line, font=fnt, fill=(0, 0, 0, 200))
        d.text((x, y), line, font=fnt, fill=(255, 255, 255, 255))
        y += 64
    return ImageClip(img).set_duration(0.1)


# ── 6. Upload to YouTube ───────────────────────────────────────────────────────
def upload_to_youtube(video: dict, video_path: Path, thumbnail_path: Path):
    creds = Credentials(
        token=None,
        refresh_token=YT_CREDS["refresh_token"],
        client_id=YT_CREDS["client_id"],
        client_secret=YT_CREDS["client_secret"],
        token_uri=YT_CREDS["token_uri"],
    )
    yt = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": video["headline"],
            "description": video["description"],
            "tags": video["tags"],
            "categoryId": "26",        # How-to & Style (closest for health)
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
            "madeForKids": False,
        },
    }

    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True, chunksize=1024 * 1024 * 5)
    request = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  ↑ Upload {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"  ✓ Uploaded: https://youtube.com/shorts/{video_id}")

    # set thumbnail
    yt.thumbnails().set(
        videoId=video_id,
        media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg"),
    ).execute()
    print(f"  ✓ Thumbnail set")

    return video_id


# ── Main pipeline ──────────────────────────────────────────────────────────────
async def process_video(video: dict):
    vid_id = video["id"]
    work_dir = OUTPUT_DIR / vid_id
    work_dir.mkdir(exist_ok=True)

    voiceover_path  = work_dir / "voiceover.mp3"
    footage_path    = work_dir / "footage.mp4"
    thumbnail_path  = work_dir / "thumbnail.jpg"
    srt_path        = work_dir / "captions.srt"
    final_path      = work_dir / "final.mp4"

    print(f"\n{'='*50}")
    print(f"Processing: {video['product']} — {video['headline']}")
    print(f"{'='*50}")

    print("\n[1/6] Generating voiceover...")
    await generate_voiceover(video["voiceover_script"], voiceover_path)

    print("\n[2/6] Downloading stock footage...")
    ok = download_pexels_video(video["pexels_query"], footage_path)
    if not ok:
        print("  ⚠ No footage found, skipping this video")
        return

    print("\n[3/6] Generating thumbnail...")
    generate_thumbnail(video["headline"], video["product"], thumbnail_path)

    print("\n[4/6] Generating captions (Whisper)...")
    generate_srt(voiceover_path, srt_path)

    print("\n[5/6] Assembling final video...")
    assemble_video(footage_path, voiceover_path, srt_path, final_path)

    print("\n[6/6] Uploading to YouTube...")
    video_id = upload_to_youtube(video, final_path, thumbnail_path)

    # mark as done in videos.json
    videos_json = BASE_DIR / "videos.json"
    data = json.loads(videos_json.read_text())
    for v in data["videos"]:
        if v["id"] == vid_id:
            v["status"] = "published"
            v["youtube_id"] = video_id
    videos_json.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    print(f"\n✅ DONE: https://youtube.com/shorts/{video_id}")


async def main():
    data = json.loads((BASE_DIR / "videos.json").read_text())
    pending = [v for v in data["videos"] if v["status"] == "pending"]

    if not pending:
        print("No pending videos. All done!")
        return

    # process one per run (to avoid rate limits)
    video = pending[0]
    await process_video(video)


if __name__ == "__main__":
    asyncio.run(main())
