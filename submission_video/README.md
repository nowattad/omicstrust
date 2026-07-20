# Submission Video Package

This directory contains the English OmicsTrust OpenAI Build Week demo package.

## Final Deliverables

- `OmicsTrust_Build_Week_Demo.mp4`: final narrated 1080p submission video.
- `captions.srt`: synchronized English captions.
- `SCRIPT_AND_STORYBOARD.md`: narration structure, scientific guardrails, and submission notes.
- `narration_segments.json`: source narration by scene.
- `slides/`: rendered 1920x1080 scene artwork.
- `assets/`: real OmicsTrust UI captures and preserved PC11 report pages.

## Rebuild

```bash
.venv/bin/pip install imageio-ffmpeg piper-tts Pillow
.venv/bin/python submission_video/build_video.py
```

The reproducible offline build uses the eSpeak-NG runtime bundled by `piper-tts` and the bundled `imageio-ffmpeg` binary. It does not upload data or call an external service.
