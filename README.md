# VFXit

VFXit (Visual Effects Exit) is a Windows desktop project for real-time webcam effects in meetings. It can hide the live camera behind a GPU-rendered smoke puff and reveal a still of the empty room. The default output is **1080p at 60 fps**.

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
| `B` | Capture the empty room after a three-second countdown |
| `Space` | Vanish in smoke and hold the captured background |
| `R` | Return to live video or cancel a pending background capture |
| `Esc` | Quit |

Use `--resolution 720 --fps 30` to set the starting mode. The webcam negotiates its own capture mode when VFXit starts. A 30 fps webcam supplies up to 30 distinct camera frames per second even when VFXit renders at 60 fps.

## Try the smoke effect

1. Run VFXit with your webcam. With the preview focused, press `B` and step out of frame before the countdown ends. Wait for **Background captured** in the terminal.
2. Sit back down and press `Space`. The smoke covers the switch to the empty-room frame. Press `R` to return to live video, including while the puff is playing.
3. Capture the background again if the camera moves or the lighting changes. VFXit keeps the background in memory for the current session.

In `--test-pattern` mode, press `Space` immediately to try the effect with a built-in reveal.

## Send the feed to a meeting

1. Install the [OBS Spout2 plug-in](https://github.com/Off-World-Live/obs-spout2-plugin) and start OBS. On dual-GPU systems, use the same graphics adapter for OBS and VFXit.
2. Start VFXit without `--preview-only`. Add a **Spout2 Capture** source in OBS and select the `VFXit` sender.
3. If you are using the test pattern, check that the orange strip appears at the top. If it appears at the bottom, restart VFXit with `--flip-spout`.
4. Match the OBS video resolution and frame rate to the VFXit output. Start **OBS Virtual Camera**, then select it as your camera in the meeting app.

VFXit prints the active GPU, measured camera resolution and frame rate, output frame rate, missed output deadlines, and Spout send errors. In a test call, verify that the other participant sees motion in the live feed, the empty-room reveal, and the immediate return to live video.

## Fix `No module named 'cv2'` on Windows

Install the dependencies and launch VFXit with the same Python interpreter inside `.venv`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe vfxit.py --test-pattern --preview-only
```

If `.venv` does not exist yet, run `python -m venv .venv` from the repository folder first.

If you launch VFXit with the **Run** button in VS Code, open the Command Palette with `Ctrl+Shift+P`, choose **Python: Select Interpreter**, and select `.venv\Scripts\python.exe`.

## Pipeline

OpenCV captures webcam frames on a worker thread. The renderer pulls the newest available frame, uploads it once, and uses GPU shaders for scaling, colour conversion, and the smoke transition. Spout shares the finished texture with OBS.
