import cv2
import numpy as np

# Define the image size
width, height = 1500, 1500  # You can adjust the size
image = np.zeros((height, width, 3), dtype=np.uint8)  # 3 channels for color
angle_offset = -23.5

# Define the circle properties
dRadius = min(width, height) // 3  # Set radius relative to image size

gRadius = dRadius * 0.75  # Set radius relative to image size

ledThickness = 32  # Thickness of the circle line

# Create a grid of x and y coordinates
y_coords, x_coords = np.indices((height, width))

# Define the radial coordinates of the image center
center_x, center_y = width // 2, height // 2

# Center the coordinates around (0,0) if necessary (optional, for center-based rotation)
x_centered = x_coords - center_x
y_centered = y_coords - center_y

# Compute the distance and angle arrays
r = np.sqrt(x_centered**2 + y_centered**2)
θ = np.arctan2(y_centered, x_centered)

# Rotation matrix
rotation_matrix = np.array(
    [
        [np.cos(np.deg2rad(90-angle_offset)), -np.sin(np.deg2rad(90-angle_offset))],
        [np.sin(np.deg2rad(90-angle_offset)), np.cos(np.deg2rad(90-angle_offset))],
    ]
)

# Apply the rotation matrix using np.einsum for simplicity
x_rotated, y_rotated = np.einsum(
    "ij, hwi -> hwj", rotation_matrix, np.stack([x_centered, y_centered], axis=-1)
).transpose(2, 0, 1)

# Create a mask for the circle
dCurveMask = (
    (dRadius - ledThickness / 2 < r)
    & (r < dRadius + ledThickness / 2)
    & (θ > np.deg2rad(-90 - angle_offset))
    & (θ < np.deg2rad(90 - angle_offset))
)

# Normalize theta to start at 0 (3 o'clock) and wrap around clockwise to 23.5 degrees
axis = (
    (np.abs(y_rotated) < ledThickness / 2)
    & (np.abs(x_rotated) < dRadius + ledThickness / 2)
    & (np.abs(x_rotated) > gRadius*1.1)
)


# Normalize theta to start at 0 (3 o'clock) and wrap around clockwise to 23.5 degrees
gCurveMask = (
    (gRadius - ledThickness / 2 < r)
    & (r < gRadius + ledThickness / 2)
    & ((np.mod(θ, 2 * np.pi)) >= np.deg2rad(0))  # 0 degrees (3 o'clock)
    & ((np.mod(θ, 2 * np.pi)) <= np.deg2rad(320))  # Wraps clockwise to 23.5 degrees
)

# Normalize theta to start at 0 (3 o'clock) and wrap around clockwise to 23.5 degrees
equator = (
    (np.abs(y_centered) < ledThickness / 2)
    & (x_centered < gRadius + ledThickness / 2)
    & (x_centered > gRadius * 0.3)
)

# Apply the mask to set the color to green
image[gCurveMask | equator] = (0, 255, 0)
# Apply the mask to set the color to blue (BGR format: (255, 0, 0))
image[dCurveMask | axis] = (255, 0, 0)
image[gCurveMask | equator] = (255, 0, 0)

# Save the image as a file
output_filename = "dglogo.png"
cv2.imwrite(output_filename, image)

print(f"Image saved as {output_filename}")
