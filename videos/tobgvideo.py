import os
import cv2

# Parameters
frame_rate = 30  # Assuming the videos have 30 FPS (adjust if needed)
duration = 3  # Extract first 3 seconds
output_filename = 'background_video.mp4'  # Output video file name

# Get all .mp4 files in the current directory
video_files = [f for f in os.listdir('.') if f.endswith('.mp4')]

# Check if any video files are found
if not video_files:
    print("No .mp4 files found in the current directory.")
    exit()

# List to store all frames
all_frames = []
width, height = None, None

# Iterate over each video and extract the first 3 seconds of frames
for video_file in video_files:
    print("processing " + video_file)
    cap = cv2.VideoCapture(video_file)
    
    if not cap.isOpened():
        print(f"Error opening video file {video_file}")
        continue

    # Get video properties
    if width is None or height is None:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(fps)

    num_frames_to_extract = int(fps * duration)

    frames_extracted = 0
    while frames_extracted < num_frames_to_extract and cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        print(frames_extracted)
        all_frames.append(frame)
        frames_extracted += 1

    cap.release()

# Define the codec and create a VideoWriter object
fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Codec for .mp4
out = cv2.VideoWriter(output_filename, fourcc, frame_rate, (width, height))

# Write all extracted frames to the output video
for frame in all_frames:
    out.write(frame)

# Release everything if job is finished
out.release()

print(f"Background video saved as {output_filename}")
