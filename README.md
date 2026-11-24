# VFXit

VFXit (Visual Effects Exit) is a Windows desktop project for real-time webcam effects in meetings. This prototype renders the camera and a test transition on the GPU and publishes the resulting texture to OBS through Spout. The default output target is **1080p at 60 fps**.

## Run on Windows

Use 64-bit Python 3.12 and a graphics driver with OpenGL 3.3 support. From the repository directory in PowerShell, run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe vfxit.py --test-pattern
```

The moving test pattern runs without opening your camera. Omit `--test-pattern` to use your webcam. Use `--camera 1` if your camera is the second device, or `--preview-only` to test the renderer without Spout.

| Key in preview | Action |
| --- | --- |
| F1 | Toggle 1080p and 720p output |
| F2 | Toggle 60 and 30 fps output |
| Space | Run the test transition |
| R | Return to the live source |
| Esc | Quit |

Use `--resolution 720 --fps 30` to set the starting mode. The in-window controls change the outgoing texture size and render cadence. The webcam negotiates its own capture mode at startup, so a camera producing 30 fps supplies at most 30 distinct camera frames per second even when the shader runs at 60 fps.

## Send the feed to a meeting

1. Install the [OBS Spout2 plug-in](https://github.com/Off-World-Live/obs-spout2-plugin) and start OBS. On dual-GPU systems, use the same graphics adapter for OBS and VFXit.
2. Add a **Spout2 Capture** source in OBS and select the `VFXit` sender. Check that the orange strip in the test pattern appears at the top. If it appears at the bottom, try `--flip-spout`.
3. Match OBS video resolution and FPS to the VFXit output, start **OBS Virtual Camera**, and select it in your meeting app.

VFXit prints the active OpenGL adapter, render loop throughput, missed output deadlines, and Spout send failures. The app's counters measure its own loop and sender. Use OBS and a second meeting participant to verify the downstream feed.

## Pipeline

OpenCV captures frames on a worker thread. The renderer pulls the newest available frame, uploads it once, and leaves scaling, colour conversion, and compositing to the shader. Spout publishes the output texture with GPU sharing enabled. The test transition gives us a repeatable workload before adding hand tracking and selectable effects.
