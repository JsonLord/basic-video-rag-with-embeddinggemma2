"""vrag command line. Pipeline order: ingest -> transcribe -> segment -> embed -> evalset -> experiments."""

import typer

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def download(n: int = 15):
    """Download the latest N channel uploads from YouTube (may be bot-blocked; prefer `ingest`)."""
    from . import download as d
    d.run(n)


@app.command()
def ingest():
    """Ingest local files from sams-videos/ (transcode to 480p, match to YouTube uploads)."""
    from . import ingest as i
    i.run()


@app.command()
def transcribe(engine: str = typer.Option(None, help="gemma (default, needs vLLM) or whisper"), force: bool = False):
    """Timestamped transcripts (creator captions if present, else Gemma 4 or Whisper)."""
    from . import transcribe as t
    from .config import ASR_ENGINE
    t.run(engine or ASR_ENGINE, force=force)


@app.command()
def switch_transcripts(engine: str):
    """Make ENGINE's transcripts active, keep segment boundaries, and re-embed the text + fused views."""
    from . import embed as e
    from . import segment as s
    from . import transcribe as t
    from .config import VIDEOS_DIR

    for vdir in sorted(p for p in VIDEOS_DIR.iterdir() if (p / "video.mp4").exists()):
        t.ensure_transcript(vdir, engine=engine, activate=True)
    s.retext()
    e.run(["text", "fused"], force=True)


@app.command()
def compare_transcripts(a: str = "whisper", b: str = "gemma"):
    """Word-level disagreement (WER of B against A) per video."""
    from . import transcribe as t
    for r in t.compare((a, b)):
        print(f"{r['wer']:.3f}  {r['words']}  {r['title']}")


@app.command()
def segment():
    """Cut ~30s segments and extract clip/audio/keyframe media."""
    from . import segment as s
    s.run()


@app.command()
def embed(view: list[str] = typer.Option(None, help="Subset of views to (re)build"), force: bool = False):
    """Embed every segment under every view with EmbeddingGemma 2."""
    from . import embed as e
    e.run(view, force=force)


@app.command()
def evalset(per_video: int = 8):
    """Generate spoken + visual eval queries with Gemma 4 (needs serve/serve.sh running)."""
    from . import evalset as ev
    ev.run(per_video)


@app.command()
def experiments():
    """Run the view x MRL-dim retrieval grid over the eval set."""
    from . import experiments as ex
    ex.run()


@app.command()
def build():
    """ingest -> transcribe -> segment -> embed."""
    ingest()
    transcribe()
    segment()
    embed()


@app.command()
def ask(question: str, view: str = "fused", dim: int = 768, k: int = 4, audio: bool = False):
    """Ask a question over the corpus from the terminal."""
    from . import rag
    res = rag.answer(question, view=view, dim=dim, k=k, use_audio=audio)
    print(res["answer"])
    for n, c in enumerate(res["clips"], 1):
        print(f"[{n}] {c['title']} @ {rag.fmt_ts(c['start'])}  (score {c['score']:.3f})")


@app.command()
def api(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """Serve the FastAPI backend for the web UI."""
    import uvicorn
    uvicorn.run("vrag.api:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
