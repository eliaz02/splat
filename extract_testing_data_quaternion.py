import json
import argparse
import sys
import os
import struct
import numpy as np

# --- HELPERS ---
def read_next_bytes(fid, num_bytes, format_char_sequence, endian_character="<"):
    data = fid.read(num_bytes)
    return struct.unpack(endian_character + format_char_sequence, data)

def qvec2rotmat(qvec):
    return np.array([
        [1 - 2 * qvec[2]**2 - 2 * qvec[3]**2,
         2 * qvec[1] * qvec[2] - 2 * qvec[0] * qvec[3],
         2 * qvec[1] * qvec[3] + 2 * qvec[0] * qvec[2]],
        [2 * qvec[1] * qvec[2] + 2 * qvec[0] * qvec[3],
         1 - 2 * qvec[1]**2 - 2 * qvec[3]**2,
         2 * qvec[2] * qvec[3] - 2 * qvec[0] * qvec[1]],
        [2 * qvec[1] * qvec[3] - 2 * qvec[0] * qvec[2],
         2 * qvec[2] * qvec[3] + 2 * qvec[0] * qvec[1],
         1 - 2 * qvec[1]**2 - 2 * qvec[2]**2]])

def rotmat2qvec(R):
    Rxx, Ryx, Rzx, Rxy, Ryy, Rzy, Rxz, Ryz, Rzz = R.flat
    K = np.array([
        [Rxx - Ryy - Rzz, 0, 0, 0],
        [Ryx + Rxy, Ryy - Rxx - Rzz, 0, 0],
        [Rzx + Rxz, Rzy + Ryz, Rzz - Rxx - Ryy, 0],
        [Ryz - Rzy, Rzx - Rxz, Rxy - Ryx, Rxx + Ryy + Rzz]]) / 3.0
    vals, vecs = np.linalg.eigh(K)
    q = vecs[:, np.argmax(vals)]
    if q[3] < 0: q = -q
    # Return as [w, x, y, z]
    return [q[3], q[0], q[1], q[2]]

# --- PARSING ---
def parse_cameras(path):
    cameras = {}
    print(f"Loading cameras from: {path}")
    
    # You can adjust these or make them arguments if needed
    TARGET_WIDTH = 1600
    TARGET_HEIGHT = 900
    
    with open(path, "rb") as fid:
        num_cameras = read_next_bytes(fid, 8, "Q")[0]
        for _ in range(num_cameras):
            camera_id = read_next_bytes(fid, 4, "I")[0]
            model_id = read_next_bytes(fid, 4, "I")[0]
            width = read_next_bytes(fid, 8, "Q")[0]
            height = read_next_bytes(fid, 8, "Q")[0]
            
            params = []
            # Model IDs: 0=SIMPLE_PINHOLE, 1=PINHOLE, 2=SIMPLE_RADIAL, 3=RADIAL
            if model_id == 0: num_params = 3
            elif model_id == 1: num_params = 4
            else: num_params = 5 # Handling others generically as 5 for safely reading

            # Read all params
            for _ in range(num_params):
                params.append(read_next_bytes(fid, 8, "d")[0])
            
            # Extract PINHOLE parameters
            if model_id == 0: # SIMPLE_PINHOLE (f, cx, cy)
                fx = fy = params[0]
                cx = params[1]
                cy = params[2]
            elif model_id == 1: # PINHOLE (fx, fy, cx, cy)
                fx = params[0]
                fy = params[1]
                cx = params[2]
                cy = params[3]
            else: 
                # Fallback for Radial/Opencv models: usually f, cx, cy are first
                fx = fy = params[0]
                cx = params[1]
                cy = params[2]

            print(f"Cam {camera_id}: {width}x{height} | fx={fx:.2f}, fy={fy:.2f}")

            cameras[camera_id] = {
                "source_width": width,
                "source_height": height,
                "fx": fx,
                "fy": fy,
                "cx": cx,
                "cy": cy,
                "output_width": TARGET_WIDTH,
                "output_height": TARGET_HEIGHT
            }
    return cameras

def parse_images(path, cameras):
    images_data = []
    
    # Transformation Matrices
    # COLMAP (OpenCV) to WebGL (OpenGL) Camera Coordinates
    # OpenCV: Right, Down, Forward (+Z)
    # WebGL:  Right, Up,   Backward (+Z is behind camera)
    # Conversion: Flip Y and Flip Z
    CV_TO_GL_CAM = np.array([
        [1,  0,  0],
        [0, 1,  0],
        [0,  0, 1]
    ])

    with open(path, "rb") as fid:
        num_reg_images = read_next_bytes(fid, 8, "Q")[0]
        for _ in range(num_reg_images):
            image_id = read_next_bytes(fid, 4, "I")[0]
            qvec = read_next_bytes(fid, 32, "dddd")
            tvec = read_next_bytes(fid, 24, "ddd")
            camera_id = read_next_bytes(fid, 4, "I")[0]
            
            name_chars = []
            while True:
                char = fid.read(1)
                if char == b"\x00": break
                name_chars.append(char)
            name = b"".join(name_chars).decode("utf-8")
            
            num_points2D = read_next_bytes(fid, 8, "Q")[0]
            fid.seek(num_points2D * 24, 1) # Skip 2D points

            # --- COORDINATE CONVERSION ---
            
            # 1. Get Rotation (World -> Camera)
            R_colmap_w2c = qvec2rotmat(qvec)
            t_colmap = np.array(tvec)

            # 2. Get Camera Position (Camera Center in World Space)
            # C = -R^T * t
            R_colmap_c2w = R_colmap_w2c.T
            pos_colmap = -np.dot(R_colmap_c2w, t_colmap)

            # 3. Apply Conversion
            # Position: Keep COLMAP World coordinates (Standard WebGL viewers usually just scale this, not flip)
            pos_gl = pos_colmap 

            # Rotation: Convert Camera Axes from CV to GL
            # R_gl = R_colmap * ConversionMatrix
            R_gl_c2w = R_colmap_c2w @ CV_TO_GL_CAM
            
            # Convert back to Quaternion [w, x, y, z]
            q_final = rotmat2qvec(R_gl_c2w)
            
            cam = cameras.get(camera_id)
            if cam:
                images_data.append({
                    "name": name,
                    "position": pos_gl.tolist(),
                    "rotation": q_final,
                    # Pass intrinsics
                    "source_width": cam["source_width"],
                    "source_height": cam["source_height"],
                    "output_width": cam["output_width"],
                    "output_height": cam["output_height"],
                    "fx": cam["fx"],
                    "fy": cam["fy"],
                    "cx": cam["cx"],
                    "cy": cam["cy"]
                })

    return images_data

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True, help="Path to COLMAP sparse folder (containing images.bin, cameras.bin)")
    parser.add_argument("--output", required=True, help="Output JSON path")
    args = parser.parse_args()
    
    images_bin = os.path.join(args.path, "images.bin")
    cameras_bin = os.path.join(args.path, "cameras.bin")

    if not os.path.exists(images_bin) or not os.path.exists(cameras_bin): 
        print(f"Error: images.bin or cameras.bin not found in {args.path}")
        sys.exit(1)
    
    cameras = parse_cameras(cameras_bin)
    data = parse_images(images_bin, cameras)
    
    # Sort by filename
    data.sort(key=lambda x: x["name"])

    with open(args.output, "w") as f: 
        json.dump(data, f, indent=4)
    
    print(f"Successfully processed {len(data)} frames to {args.output}")

if __name__ == "__main__":
    main()