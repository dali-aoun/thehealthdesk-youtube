# Local script: generate all voiceovers once and commit to repo.
import asyncio, json
from pathlib import Path
import edge_tts

BASE_DIR   = Path(__file__).parent.parent
VOICES_DIR = BASE_DIR / "assets" / "voiceovers"
VOICES_DIR.mkdir(parents=True, exist_ok=True)

videos = json.loads((BASE_DIR / "videos.json").read_text(encoding="utf-8"))["videos"]

async def gen(text: str, out: Path):
    c = edge_tts.Communicate(text, voice="en-US-GuyNeural", rate="+5%", volume="+10%")
    await c.save(str(out))
    print(f"  OK {out.name}")

async def main():
    for v in videos:
        out = VOICES_DIR / f"{v['id']}.mp3"
        if out.exists():
            print(f"  skip (exists): {out.name}")
            continue
        print(f"Generating {v['id']} — {v['product']}...")
        await gen(v["voiceover_script"], out)

asyncio.run(main())
print("\nAll voiceovers done. Now run: git add assets/voiceovers && git commit -m 'feat: add pre-generated voiceovers' && git push")
