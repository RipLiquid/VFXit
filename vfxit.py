"""VFXit GPU camera prototype for Windows."""

import argparse
import sys
from threading import Event, Lock, Thread
from time import perf_counter

import cv2
import glfw
import moderngl


GL_TEXTURE_2D = 0x0DE1
VERTEX_SHADER = """
#version 330
out vec2 uv;
void main() {
    vec2 point = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    uv = point;
    gl_Position = vec4(point * 2.0 - 1.0, 0.0, 1.0);
}
"""
COMPOSITE_SHADER = """
#version 330
uniform sampler2D camera;
uniform bool have_camera;
uniform bool test_pattern;
uniform float camera_aspect;
uniform float output_aspect;
uniform float time;
uniform float transition;
in vec2 uv;
out vec4 color;
void main() {
    vec3 live = vec3(0.025, 0.035, 0.055);
    if (test_pattern) {
        vec3 bars = 0.53 + 0.32 * cos(floor(uv.x * 8.0) + vec3(0, 2, 4));
        float marker = 1.0 - step(0.025, abs(uv.x - fract(time * 0.5)));
        live = mix(bars * (0.35 + uv.y * 0.65), vec3(1.0), marker);
        if (uv.y > 0.92) live = vec3(0.95, 0.32, 0.12);
    } else if (have_camera) {
        vec2 scale = max(vec2(output_aspect / camera_aspect,
                              camera_aspect / output_aspect), vec2(1.0));
        vec2 p = (uv - 0.5) * scale + 0.5;
        if (all(greaterThanEqual(p, vec2(0.0))) && all(lessThanEqual(p, vec2(1.0)))) {
            live = texture(camera, vec2(p.x, 1.0 - p.y)).bgr;
        }
    }
    vec3 reveal = vec3(0.05, 0.10, 0.17) + vec3(0.04, 0.12, 0.13) * uv.y;
    float sweep = smoothstep(-0.025, 0.025, transition * 1.06 - 0.03 - uv.x);
    color = vec4(mix(live, reveal, sweep), 1.0);
}
"""
PREVIEW_SHADER = """
#version 330
uniform sampler2D output_texture;
in vec2 uv;
out vec4 color;
void main() { color = texture(output_texture, uv); }
"""


class Camera:
    def __init__(self, index, width, height, fps):
        self.stop = Event()
        self.lock = Lock()
        self.latest = (0, None, 0.0)
        self.error = None
        self.worker = Thread(target=self.capture, args=(index, width, height, fps), daemon=True)
        self.worker.start()

    def capture(self, index, width, height, fps):
        device = None
        try:
            for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF):
                device = cv2.VideoCapture(index, backend)
                if device.isOpened():
                    break
                device.release()
            else:
                self.error = f"Could not open webcam {index}. Check permissions or use --camera."
                return
            device.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            device.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            device.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            device.set(cv2.CAP_PROP_FPS, fps)
            frames = 0
            start = perf_counter()
            input_fps = 0.0
            sequence = 0
            while not self.stop.is_set():
                ok, frame = device.read()
                if not ok:
                    self.error = "Webcam stopped delivering frames. Check the connection and restart."
                    return
                sequence += 1
                frames += 1
                elapsed = perf_counter() - start
                if elapsed >= 1.0:
                    input_fps = frames / elapsed
                    frames = 0
                    start = perf_counter()
                with self.lock:
                    self.latest = (sequence, frame, input_fps)
        except cv2.error as error:
            self.error = f"Webcam error: {error}"
        finally:
            if device is not None:
                device.release()

    def snapshot(self):
        with self.lock:
            return self.latest

    def close(self):
        self.stop.set()
        self.worker.join(timeout=2)


def run(args):
    if not glfw.init():
        raise RuntimeError("Could not initialize GLFW. Run VFXit in a Windows desktop session.")

    camera = None
    sender = None
    window = None
    try:
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        window = glfw.create_window(960, 540, "VFXit Output", None, None)
        if window is None:
            raise RuntimeError("Could not create an OpenGL 3.3 window. Check your graphics driver.")
        glfw.make_context_current(window)
        glfw.swap_interval(0)
        context = moderngl.create_context(require=330)
        renderer = context.info["GL_RENDERER"]
        print(f"OpenGL renderer: {renderer}", flush=True)
        if any(name in renderer.lower() for name in ("llvmpipe", "softpipe", "software", "gdi generic")):
            raise RuntimeError("Software OpenGL detected. Select a hardware GPU and restart VFXit.")

        composite = context.program(vertex_shader=VERTEX_SHADER, fragment_shader=COMPOSITE_SHADER)
        preview = context.program(vertex_shader=VERTEX_SHADER, fragment_shader=PREVIEW_SHADER)
        composite_quad = context.vertex_array(composite, [])
        preview_quad = context.vertex_array(preview, [])
        camera_texture = context.texture((1, 1), 3)
        output_texture = None
        output_buffer = None
        width, height = (1920, 1080) if args.resolution == 1080 else (1280, 720)
        fps = args.fps
        transition_start = None

        if not args.preview_only:
            import SpoutGL

            sender = SpoutGL.SpoutSender()
            sender.setSenderName("VFXit")
            sender.setAutoShare(False)
            sender.setCPUshare(False)
        if not args.test_pattern:
            camera = Camera(args.camera, width, height, args.fps)

        def on_key(key_window, key, scancode, action, mods):
            nonlocal width, height, fps, transition_start
            if action != glfw.PRESS:
                return
            if key == glfw.KEY_F1:
                width, height = (1280, 720) if height == 1080 else (1920, 1080)
            elif key == glfw.KEY_F2:
                fps = 30 if fps == 60 else 60
            elif key == glfw.KEY_SPACE:
                transition_start = perf_counter()
            elif key == glfw.KEY_R:
                transition_start = None
            elif key == glfw.KEY_ESCAPE:
                glfw.set_window_should_close(key_window, True)

        glfw.set_key_callback(window, on_key)
        print("F1 resolution | F2 frame rate | Space test transition | R return live | Esc quit", flush=True)
        start = last_report = deadline = perf_counter()
        sequence = rendered = missed = failed_sends = 0
        input_fps = 0.0
        worst_ms = 0.0
        spout_verified = False
        measured_mode = (width, height, fps)

        while not glfw.window_should_close(window):
            glfw.poll_events()
            if glfw.window_should_close(window):
                break
            now = perf_counter()
            mode = (width, height, fps)
            if mode != measured_mode:
                measured_mode = mode
                last_report = deadline = now
                rendered = missed = failed_sends = 0
                worst_ms = 0.0
            if now < deadline:
                glfw.wait_events_timeout(deadline - now)
                continue
            period = 1 / fps
            skipped = int((now - deadline) / period)
            missed += skipped
            deadline += (skipped + 1) * period

            if camera is not None:
                if camera.error:
                    raise RuntimeError(camera.error)
                frame_sequence, frame, input_fps = camera.snapshot()
                if frame_sequence != sequence:
                    frame_height, frame_width = frame.shape[:2]
                    if camera_texture.size != (frame_width, frame_height):
                        camera_texture.release()
                        camera_texture = context.texture((frame_width, frame_height), 3)
                    camera_texture.write(memoryview(frame), alignment=1)
                    sequence = frame_sequence

            if output_texture is None or output_texture.size != (width, height):
                if output_buffer is not None:
                    output_buffer.release()
                    output_texture.release()
                output_texture = context.texture((width, height), 4)
                output_buffer = context.framebuffer(color_attachments=[output_texture])

            output_buffer.use()
            context.viewport = (0, 0, width, height)
            camera_texture.use(location=0)
            composite["camera"].value = 0
            composite["test_pattern"].value = args.test_pattern
            composite["have_camera"].value = sequence > 0
            composite["camera_aspect"].value = camera_texture.width / camera_texture.height
            composite["output_aspect"].value = width / height
            composite["time"].value = now - start
            composite["transition"].value = 0.0 if transition_start is None else min(1.0, (now - transition_start) / 0.65)
            composite_quad.render(moderngl.TRIANGLES, vertices=3)

            if sender is not None:
                sent = sender.sendTexture(
                    output_texture.glo, GL_TEXTURE_2D, width, height,
                    not args.flip_spout, output_buffer.glo,
                )
                if not sent:
                    failed_sends += 1
                elif not spout_verified:
                    if not sender.isGLDXReady() or sender.getCPUshare():
                        raise RuntimeError("Spout GPU texture sharing is unavailable. Select the same GPU in VFXit and OBS, or run --preview-only.")
                    print("Spout GPU texture sharing active: VFXit", flush=True)
                    spout_verified = True

            window_width, window_height = glfw.get_framebuffer_size(window)
            if window_width > 0 and window_height > 0:
                context.screen.use()
                context.screen.clear(0.025, 0.035, 0.055)
                scale = min(window_width / width, window_height / height)
                fitted_width, fitted_height = int(width * scale), int(height * scale)
                context.viewport = ((window_width - fitted_width) // 2, (window_height - fitted_height) // 2, fitted_width, fitted_height)
                output_texture.use(location=0)
                preview["output_texture"].value = 0
                preview_quad.render(moderngl.TRIANGLES, vertices=3)
                glfw.swap_buffers(window)

            rendered += 1
            finished = perf_counter()
            worst_ms = max(worst_ms, (finished - now) * 1000)
            elapsed = finished - last_report
            if elapsed >= 1.0:
                source = "test pattern" if args.test_pattern else f"camera {input_fps:.1f} fps"
                report = f"{width}x{height}@{fps} | {source} | output {rendered / elapsed:.1f} fps | missed {missed} | worst render loop {worst_ms:.1f} ms"
                if sender is not None:
                    report += f" | Spout send errors {failed_sends}"
                glfw.set_window_title(window, f"VFXit Output | {report}")
                print(report, flush=True)
                last_report = finished
                rendered = missed = failed_sends = 0
                worst_ms = 0.0
            if args.seconds is not None and finished - start >= args.seconds:
                break
    finally:
        if camera is not None:
            camera.close()
        if sender is not None:
            sender.releaseSender()
        if window is not None:
            glfw.destroy_window(window)
        glfw.terminate()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0, help="Windows webcam index")
    parser.add_argument("--resolution", choices=(720, 1080), type=int, default=1080)
    parser.add_argument("--fps", choices=(30, 60), type=int, default=60)
    parser.add_argument("--test-pattern", action="store_true", help="Use an animated GPU test pattern in place of the webcam")
    parser.add_argument("--preview-only", action="store_true", help="Run without a Spout sender")
    parser.add_argument("--flip-spout", action="store_true", help="Reverse the default vertical orientation of the Spout stream")
    parser.add_argument("--seconds", type=float, help="Exit after this many seconds (for smoke testing)")
    args = parser.parse_args()
    if args.seconds is not None and args.seconds <= 0:
        parser.error("--seconds must be positive")
    try:
        run(args)
    except (RuntimeError, ImportError, moderngl.Error) as error:
        print(f"VFXit: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
