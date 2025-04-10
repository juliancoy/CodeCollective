import numpy as np
import cv2

def quadrupleMirror(image):
    image = np.concatenate(
        (image, np.flip(image, axis=0)), axis=0, out=None, dtype=None, casting="same_kind"
    )
    image = np.concatenate(
        (image, np.flip(image, axis=1)), axis=1, out=None, dtype=None, casting="same_kind"
    )
    return image


# convert the circle form back to cartesian
def radial_unity_to_cartesian(radial_data, height, width):
    # Extract r_unity and t_unity from the combined array
    t_unity = radial_data[..., 0]
    r_unity = radial_data[..., 1]

    centerY = int(height / 2)
    centerX = int(width / 2)
    max_dim = min(width/2, height/2) -1

    # Denormalize radial coordinates
    r = r_unity * max_dim

    # Denormalize angular coordinates
    t = t_unity * (2 * np.pi) - (np.pi)

    # Convert back to Cartesian coordinates
    xx = r * np.cos(t) + centerX
    yy = r * np.sin(t) + centerY

    # Combine into a single array of shape (height, width, 2)
    result = np.stack((xx, yy), axis=-1)

    return result

# draws the largest possible unity circle on the input image
def cartesian_to_radial_unity(height, width):
    centerY = int(height / 2)
    centerX = int(width / 2)

    xvalues = np.arange(width)
    yvalues = np.arange(height)
    xx, yy = np.meshgrid(xvalues, yvalues)

    xx -= centerX
    yy -= centerY

    # Convert to radial coords
    r = np.sqrt(xx**2 + yy**2)
    r_unity = r / min(width/2, height/2)

    t = np.arctan2(yy, xx)

    # Normalize T to [0, 1)
    t_unity = (t + np.pi) / (2 * np.pi)

    # Combine into a single array of shape (height, width, 2)
    result = np.stack((t_unity, r_unity), axis=-1)

    return result

#def updateR(self, phase):
#    r_adjust = np.fmod(self.r/(self.width/2) - phase, 1)
#    self.r_unity = (r_adjust*self.width).astype(int)

import sys
if __name__ == "__main__":
    filename = sys.argv[1]
    output_video = filename + "_output.mp4"  # Output video file name
    output_image = filename + "_output.png"
    frame_count = 300

    input_image = cv2.imread(filename)
    input_image = quadrupleMirror(input_image)
    input_height, input_width = input_image.shape[:2]

    output_width = 1080
    output_height = 1920

    output_frame_size = (output_width, output_height)  # Replace with your image dimensions
    fps = 30  # Frames per second

    # Initialize VideoWriter
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # Use a codec (e.g., XVID, MP4V)
    video_writer = cv2.VideoWriter(output_video, fourcc, fps, output_frame_size)
    #input_r_unity, input_t_unity = compute_unity_coordinates(height=input_height,width=input_width)
    output_coords_radial = cartesian_to_radial_unity(height=output_height,width=output_width)
    #modular system on radius
    output_coords_radial[:,:,0] *= 12
    repititions = 3
    #original_r = np.fmod(output_coords_radial[:,:,1],1)
    phase = 0
    output_coords_radial[:,:,0] += 0.25
    phase = repititions * (1 / frame_count)

    for j in range(frame_count):
        print(f"   {j} {phase}")
        
        output_coords_radial[:,:,1] = np.fmod(output_coords_radial[:,:,1] + phase, 1)
        thisoutput = np.copy(output_coords_radial)
        #thisoutput[:,:,1] = np.power(output_coords_radial[:,:,1], 5)
        
        sample_coords = radial_unity_to_cartesian(thisoutput, input_width, input_height).astype(int)

        # Split the sample_coords into separate y and x indices (to keep from killing the computer)
        y_indices = sample_coords[..., 0].astype(int)  # Extract y-coordinates
        x_indices = sample_coords[..., 1].astype(int)  # Extract x-coordinates
        #debug_image = (y_indices * 255).astype(np.uint8)
        #cv2.imshow("Debug", cv2.resize(debug_image,(200,200)))
        #cv2.waitKey(0)  # Wait for 1 ms to update the display


        mandala_img = input_image[y_indices, x_indices]

        # Create a grayscale image where pixel intensity corresponds to r_unity
        cv2.imshow("Debug", cv2.resize(mandala_img,(200,200)))
        cv2.waitKey(1)  # Wait for 1 ms to update the display

        # Ensure the generated image has the correct size
        if mandala_img.shape[1] != output_frame_size[0] or mandala_img.shape[0] != output_frame_size[1]:
            raise(Exception(f"Wrong Size {mandala_img.shape, output_frame_size}"))
        
        # Write frame to video
        video_writer.write(mandala_img)

    # Release the VideoWriter
    video_writer.release()
    print(f"Video saved as {output_video}")