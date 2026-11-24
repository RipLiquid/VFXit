# VFXit

VFXit (Visual Effects Exit) is a Windows desktop project for real-time webcam effects in meetings. This prototype renders the camera and a test transition on the GPU and publishes the output texture to OBS through Spout. The default output is **1080p at 60 fps**.

## Run on Windows

Use 64-bit Python 3.12 and a graphics driver with OpenGL 3.3 support. From the repository folder in PowerShell, run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe vfxit.py --test-pattern --preview-only
```

The moving test pattern lets you check the renderer without a webcam or OBS. Omit `--test-pattern` to use your webcam, or add `--camera 1` to try the second camera. Remove `--preview-only` to publish the feed to Spout.

| Key in the preview window | Action |
| --- | --- |
| `F1` | Toggle between 1080p and 720p output |
| `F2` | Toggle between 60 and 30 fps output |
| `Space` | Run the test transition |
| `R` | Return to the live source |
| `Esc` | Quit |

Use `--resolution 720 --fps 30` to set the starting mode. The webcam negotiates its own capture mode when VFXit starts. A 30 fps webcam supplies up to 30 distinct camera frames per second even when VFXit renders at 60 fps.

## Send the feed to a meeting

1. Install the [OBS Spout2 plug-in](https://github.com/Off-World-Live/obs-spout2-plugin) and start OBS. On dual-GPU systems, use the same graphics adapter for OBS and VFXit.
2. Start VFXit without `--preview-only`. Add a **Spout2 Capture** source in OBS and select the `VFXit` sender.
3. If you are using the test pattern, check that the orange strip appears at the top. If it appears at the bottom, restart VFXit with `--flip-spout`.
4. Match the OBS video resolution and frame rate to the VFXit output. Start **OBS Virtual Camera**, then select it as your camera in the meeting app.

VFXit prints the active GPU, output frame rate, missed output deadlines, and Spout send errors. Use OBS and a second meeting participant to verify what the meeting receives.

## Fix `No module named 'cv2'` on Windows

Install the dependencies and launch VFXit with the same Python interpreter inside `.venv`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe vfxit.py --test-pattern --preview-only
```

If `.venv` does not exist yet, run `python -m venv .venv` from the repository folder first.

If you launch VFXit with the **Run** button in VS Code, open the Command Palette with `Ctrl+Shift+P`, choose **Python: Select Interpreter**, and select `.venv\Scripts\python.exe`.

## Pipeline

OpenCV captures webcam frames on a worker thread. The renderer pulls the newest available frame, uploads it once, and uses a GPU shader for scaling, colour conversion, and compositing. Spout shares the finished texture with OBS. The test transition provides a repeatable workload for measuring performance before adding hand tracking and selectable effects.