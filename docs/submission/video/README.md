# Editable BlastGate technical demo

The authoritative timeline is [project.json](project.json), with [storyboard](STORYBOARD.md), [narration](narration.md) and [SRT subtitles](subtitles.srt). [render_media.ps1](render_media.ps1) uses local FFmpeg, System.Drawing and the installed Microsoft Zira Desktop voice. No paid service or music is used.

From a normal Windows PowerShell session at the repository root:

```powershell
./docs/submission/video/render_media.ps1 -Ffmpeg 'PATH_TO_EXISTING_FFMPEG' -Ffprobe 'PATH_TO_EXISTING_FFPROBE'
```

Supply paths to existing binaries; none are distributed in the public package. `-ImagesOnly` regenerates the contact sheet and scene compositions. `-SkipSpeech` reuses already generated WAV clips when voice access is restricted in the rendering process. Temporary compositions/audio/clips live under the ignored `.local/stage2/video-work` folder.

Output: `media-exports/blastgate-demo-120s.mp4`, 120 seconds, 1920×1080, 30 fps, H.264 with AAC narration and burned subtitles. The export stays outside normal Git tracking until hosting is decided. Representative actual decoded video frames are saved under `docs/submission/assets/final/video-frames/`.

The project combines real browser still captures with subtle camera movement, fades and explanatory architecture highlights. It is an edited demonstration, not a continuous screen recording or a new AWS execution. The timeline does not assert intermediate event timestamps, measured performance or unobserved model refusals.
