# splat — Sky Rendering Fork

A fork of [antimatter15/splat](https://github.com/antimatter15/splat) — a WebGL real-time renderer for [3D Gaussian Splatting](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/).

This fork extends the original viewer with **sky map rendering** capabilities, used as part of the [Sky-Map-in-3D-Gaussian-Splatting](https://github.com/eliaz02/Sky-Map-in-3D-Gaussian-Splatting) project.

## What's Changed

### Sky Rendering in `main.js`

The core rendering pipeline has been modified (~630 lines added) to support rendering a latitude-longitude sky map behind the Gaussian splat scene:

- **Skybox integration** — Renders an equirectangular sky map as the scene background, visible through transparent regions of the Gaussian splats
- **Camera-relative sky projection** — The sky texture is sampled based on world-space view direction, ensuring correct sky appearance from any camera angle
- **Image capture** — Added functionality to render and save images from specific camera viewpoints for comparison against ground truth

### COLMAP Data Extraction (`extract_testing_data_quaternion.py`)

A utility script that extracts camera data from COLMAP's binary output files (`images.bin`, `cameras.bin`) and converts it to a JSON format compatible with the viewer:

- Parses COLMAP binary camera models (SIMPLE_PINHOLE, PINHOLE, RADIAL, etc.)
- Converts COLMAP world-to-camera transforms to camera-to-world poses
- Handles coordinate system conversion (OpenCV → OpenGL conventions)
- Outputs camera positions, rotations (as quaternions), and intrinsics

**Usage:**
```bash
python extract_testing_data_quaternion.py \
    --path /path/to/colmap/sparse/0 \
    --output cameras.json
```

**Output format:**
```json
[
    {
        "name": "image_001.png",
        "position": [x, y, z],
        "rotation": [w, x, y, z],
        "source_width": 1920,
        "source_height": 1080,
        "output_width": 1600,
        "output_height": 900,
        "fx": 1200.0,
        "fy": 1200.0,
        "cx": 960.0,
        "cy": 540.0
    }
]
```

## Original Features

All original features from [antimatter15/splat](https://github.com/antimatter15/splat) are preserved:

- WebGL 1.0 real-time Gaussian splatting renderer
- No external dependencies
- Progressive loading with async CPU sorting
- Drag-and-drop `.ply` → `.splat` conversion
- Full camera controls (keyboard, mouse, trackpad, touch)

### Controls

**Movement** (arrow keys): strafe (←→), forward/back (↑↓), jump (space)

**Camera** (WASD): turn (A/D), tilt (W/S), roll (Q/E), orbit (I/K, J/L)

**Mouse**: drag to orbit, right-click drag to move

**Other**: 0-9 for preset views, `P` for animation, `V` to save view, drag `.ply`/`.splat` files to load

## Acknowledgements

Original viewer by [antimatter15](https://github.com/antimatter15). See the [original README](https://github.com/antimatter15/splat#acknowledgements) for full acknowledgements.
