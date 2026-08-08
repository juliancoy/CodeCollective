import cv2
import numpy as np
from datetime import datetime, timezone
from PIL import ImageFont, ImageDraw, Image, ImageOps
import qrcode
import textwrap
import re
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import io
import base64
import os
import logging
import sys
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
import env

here = os.path.abspath(os.path.dirname(__file__))

y_draw = 20

if os.getenv("LOG_LEVEL"):
    log_level = os.getenv("LOG_LEVEL")
else:
    log_level = "DEBUG"

numeric_level = getattr(logging, log_level.upper(), None)
if not isinstance(numeric_level, int):
    raise ValueError(f"Invalid log level: {log_level}")

logging.basicConfig(
    level=numeric_level,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)


def upload_to_s3(file_path, bucket_name, s3_key):
    """
    Uploads a file to an S3 bucket.
    :param file_path: Path to the file to upload.
    :param bucket_name: Name of the S3 bucket.
    :param s3_key: Key (path) in the S3 bucket where the file will be stored.
    :return: True if the upload was successful, False otherwise.
    """
    # Initialize the S3 client
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=env.aws_access_key_id,
        aws_secret_access_key=env.aws_secret_access_key,
        region_name=env.aws_default_region,
    )

    # Upload the file
    s3_client.upload_file(file_path, bucket_name, s3_key)
    logging.debug(f"File uploaded successfully to s3://{bucket_name}/{s3_key}")
    return f"s3://{bucket_name}/{s3_key}"


def update_dynamodb_table(timename, timestamp, name, table_name, imageurl):
    # Create a DynamoDB resource
    dynamodb = boto3.resource(
        "dynamodb",
        aws_access_key_id=env.aws_access_key_id,
        aws_secret_access_key=env.aws_secret_access_key,
        region_name=env.aws_default_region,
    )

    # Get the table
    table = dynamodb.Table(table_name)

    # Update the item in the table, including the image URL
    response = table.update_item(
        Key={"timename": timename},
        UpdateExpression="SET #time = :time, #name = :name, #imageurl = :imageurl",
        ExpressionAttributeNames={
            "#time": "time",
            "#name": "name",
            "#imageurl": "imageurl"
        },
        ExpressionAttributeValues={
            ":time": timestamp,
            ":name": name,
            ":imageurl": imageurl
        },
        ReturnValues="UPDATED_NEW",
    )

    logging.debug("UpdateItem succeeded:")
    logging.debug(response)
    return response


# Function to load a private key from an environment variable
def load_private_key_from_env():
    # Get the private key from the environment variable
    private_key_pem = base64.b64decode(env.privkey_base64).decode("utf-8")

    # Load the private key
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode(),  # Convert string to bytes
        password=None,  # Add a password if the key is encrypted
        backend=default_backend(),
    )
    return private_key


# Step 1: Load the PNG image
def sign_image(image_path):
    image = Image.open(image_path)

    # Convert the image to bytes
    image_bytes = io.BytesIO()
    image.save(image_bytes, format="WEBP")
    image_data = image_bytes.getvalue()

    private_key = load_private_key_from_env()

    # Sign the image data
    signature = private_key.sign(
        image_data,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256(),
    )

    # Step 3: Embed the signature in the image metadata
    # Convert the signature to a hex string for storage
    signature_hex = signature.hex()

    # Add the signature to the image's metadata
    image.info["signature"] = signature_hex

    # Save the image with the embedded signature
    signed_image_path = image_path
    image.save(signed_image_path, format="WEBP")

    logging.debug(f"Image signed and saved successfully to '{signed_image_path}'!")
    logging.debug(f"Signature embedded in metadata: {signature_hex}")


def break_into_lines(text, max_length=20):
    # Define a regex pattern to split on punctuation (except apostrophes and other pronunciation marks)
    pattern = r"[\s,.;:!?\-—]|\\x[0-9A-Fa-f]{2}"
    # Split the text into parts based on the pattern
    parts = re.split(pattern, text)

    # Reconstruct the text with spaces around punctuation for proper wrapping
    reconstructed_text = " ".join([part if part.strip() else " " for part in parts])

    # Use textwrap to wrap the text into lines of max_length
    wrapped_lines = textwrap.wrap(
        reconstructed_text, width=max_length, break_long_words=False
    )

    return wrapped_lines


def fit_text_lines(
    draw,
    text,
    font_path,
    max_width,
    max_height,
    start_size,
    min_size=18,
    line_spacing_ratio=0.22,
):
    words = text.split()
    font_size = start_size
    while font_size >= min_size:
        font = ImageFont.truetype(font_path, font_size)
        lines = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            bbox = font.getbbox(candidate)
            if (bbox[2] - bbox[0]) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)

        spacing = max(8, int(font_size * line_spacing_ratio))
        line_heights = []
        line_widths = []
        total_height = 0
        for line in lines:
            bbox = font.getbbox(line)
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            line_widths.append(width)
            line_heights.append(height)
            total_height += height
        total_height += spacing * max(0, len(lines) - 1)

        if lines and max(line_widths) <= max_width and total_height <= max_height:
            return font, lines, spacing, line_heights, total_height
        font_size -= 2

    raise ValueError(f"Text cannot fit within bounds: {text}")


def draw_centered_block(
    draw,
    center_x,
    center_y,
    text,
    font_path,
    fill,
    max_width,
    max_height,
    start_size,
    min_size=18,
    line_spacing_ratio=0.22,
):
    font, lines, spacing, line_heights, total_height = fit_text_lines(
        draw,
        text,
        font_path,
        max_width,
        max_height,
        start_size,
        min_size=min_size,
        line_spacing_ratio=line_spacing_ratio,
    )
    y = center_y - total_height / 2
    for idx, line in enumerate(lines):
        bbox = font.getbbox(line)
        width = bbox[2] - bbox[0]
        draw.text((center_x - width / 2, y), line, font=font, fill=fill)
        y += line_heights[idx] + spacing
    return font


def draw_centered_text(draw, center_x, y_top, text, font, fill):
    bbox = font.getbbox(text)
    text_width = bbox[2] - bbox[0]
    draw.text((center_x - text_width / 2, y_top), text, font=font, fill=fill)


def build_hex_mask(image_size):
    center = (image_size // 2, image_size // 2)
    radius = image_size // 2.05
    hexagon = []
    for i in range(6):
        angle = np.deg2rad(i * 60)
        x = int(center[0] + radius * np.cos(angle))
        y = int(center[1] + radius * np.sin(angle))
        hexagon.append((x, y))
    hexagon = np.array(hexagon, dtype=np.int32)
    mask = np.zeros((image_size, image_size), dtype=np.uint8)
    cv2.fillPoly(mask, [hexagon], color=255)
    return hexagon, mask


def draw_gradient_hex(image_size):
    image = np.zeros((image_size, image_size, 4), dtype=np.uint8)
    hexagon, mask = build_hex_mask(image_size)
    mask_points = np.where(mask > 0)
    y_coords, x_coords = mask_points
    top_color = np.array([63, 97, 226, 255])
    bottom_color = np.array([6, 14, 40, 255])
    alpha = y_coords / float(image_size)
    gradient_colors = (
        (1 - alpha[:, None]) * top_color + alpha[:, None] * bottom_color
    ).astype(np.uint8)
    image[y_coords, x_coords] = gradient_colors
    cv2.polylines(
        image, [hexagon], isClosed=True, color=(255, 255, 255, 255), thickness=13
    )
    cv2.polylines(
        image, [hexagon], isClosed=True, color=(221, 231, 255, 255), thickness=4
    )
    return Image.fromarray(image), hexagon, mask


def add_photo_frame(base_image, image_path, left, top, size):
    person_image = Image.open(image_path).convert("RGB")
    framed = Image.new("RGBA", (size, size), (248, 248, 248, 255))
    inner_margin = 18
    photo = ImageOps.fit(
        person_image,
        (size - inner_margin * 2, size - inner_margin * 2),
        method=Image.LANCZOS,
    ).convert("RGBA")
    framed.paste(photo, (inner_margin, inner_margin))
    base_image.paste(framed, (left, top), framed)


def drawTextCenteredFit(
    draw,
    image_size,
    text,
    font_path,
    fill,
    max_width=550,
    max_height=300,
    y_center=250,
    font_size=180,
):
    og_font_size = font_size
    spacing = font_size / 18  # Spacing between lines
    lines = []

    # Break text into lines
    for line in break_into_lines(text, max_length=15 + len(text) / 5):
        lines.append({"content": line})
    logging.debug(lines)
    # Adjust font size until the text fits within the bounds
    while True:
        font = ImageFont.truetype(font_path, font_size)
        total_height = 0
        max_line_width = 0

        # Calculate the total height and maximum line width
        for line in lines:
            bbox = font.getbbox(line["content"])
            line["width"] = bbox[2] - bbox[0]
            line["height"] = bbox[3] - bbox[1]
            total_height += line["height"] + spacing
            if line["width"] > max_line_width:
                max_line_width = line["width"]

        # Check if the text fits within the bounds
        if max_line_width <= max_width and total_height <= max_height:
            break
        else:
            # Reduce the font size and try again
            font_size -= 1
            if font_size < 1:
                raise ValueError("Text cannot fit within the specified bounds.")
            else:
                spacing = 10 * font_size / og_font_size

    # Calculate the starting y-position for vertical centering
    total_height -= spacing  # Remove the last spacing
    ypos = y_center - (total_height / 2)

    # Draw the text line by line
    for line in lines:
        bbox = font.getbbox(line["content"])
        x = (image_size - line["width"]) // 2  # Center horizontally
        draw.text((x, ypos), line["content"], font=font, fill=fill)
        ypos += line["height"] + spacing  # Add spacing between lines


def drawTextCentered(draw, image_size, text, font, fill):
    global y_draw
    """Draw text centered horizontally on the given y-coordinate."""
    # Use font.getbbox for text dimensions
    bbox = font.getbbox(text)
    text_width = bbox[2] - bbox[0]  # Calculate width from bounding box
    text_height = bbox[3] - bbox[1]  # Calculate height from bounding box
    x = (image_size - text_width) // 2  # Calculate horizontal center
    draw.text((x, y_draw), text, font=font, fill=fill)
    y_draw += text_height + 20


def generate_badge(imagefilename, name, citation_text, tablename):
    time = datetime.now(timezone.utc)  # Get the current time in UTC
    timestamp = time.strftime("%Y-%m-%d_%H:%M:%S_%Z")  # Include timezone name
    display_date = time.strftime("%B %d, %Y")

    global y_draw
    y_draw = 30
    image_size = 1920

    font_path = os.path.join(here, "nofile")
    pil_image, hexagon, mask = draw_gradient_hex(image_size)
    draw = ImageDraw.Draw(pil_image)

    # Sanitize the name to be file-friendly
    safe_name = re.sub(r"[^\w\-_. ]", "_", name).replace(
        " ", "_"
    )  # Replace invalid characters with '_'
    safe_name = safe_name[:50]
    timename = (f"{timestamp}_{safe_name}")[:255]
    output_file = os.path.join(here, "cert_image", f"{timename}_badge.webp").replace(
        ":", "-"
    )
    os.makedirs(os.path.join(here, "cert_image"), exist_ok=True)
    logging.debug(output_file)

    # Header
    draw_centered_block(
        draw,
        image_size / 2,
        image_size * 0.11,
        "Code Collective",
        font_path,
        (255, 255, 255, 235),
        max_width=image_size * 0.44,
        max_height=90,
        start_size=64,
        min_size=44,
        line_spacing_ratio=0.14,
    )
    draw_centered_block(
        draw,
        image_size / 2,
        image_size * 0.205,
        "Certificate of Appreciation",
        font_path,
        (255, 255, 255, 255),
        max_width=image_size * 0.56,
        max_height=190,
        start_size=94,
        min_size=52,
        line_spacing_ratio=0.1,
    )
    draw_centered_block(
        draw,
        image_size / 2,
        image_size * 0.30,
        "Presented To",
        font_path,
        (232, 239, 255, 230),
        max_width=image_size * 0.42,
        max_height=60,
        start_size=44,
        min_size=28,
        line_spacing_ratio=0.1,
    )

    draw_centered_block(
        draw,
        image_size / 2,
        image_size * 0.39,
        text=name,
        font_path=font_path,
        fill=(255, 255, 255, 255),
        max_width=image_size * 0.66,
        max_height=image_size * 0.16,
        start_size=120,
        min_size=54,
        line_spacing_ratio=0.08,
    )

    draw_centered_block(
        draw,
        image_size / 2,
        image_size * 0.54,
        citation_text,
        font_path,
        (255, 255, 255, 255),
        max_width=image_size * 0.62,
        max_height=image_size * 0.12,
        start_size=46,
        min_size=26,
        line_spacing_ratio=0.14,
    )
    draw_centered_block(
        draw,
        image_size / 2,
        image_size * 0.61,
        display_date,
        font_path,
        (232, 239, 255, 220),
        max_width=image_size * 0.28,
        max_height=34,
        start_size=22,
        min_size=18,
        line_spacing_ratio=0.1,
    )

    # Generate QR code
    verify_url = f"https://codecollective.us/verify.html?timename={timename}&tablename={tablename}"
    logging.debug(f"Verify URL: {verify_url}")
    qr = qrcode.QRCode(box_size=10, border=1)
    qr.add_data(verify_url)
    qr.make(fit=True)
    qr_image = qr.make_image(fill="black", back_color="white").convert("RGBA")

    # Insert QR code into the badge
    qr_len = 400
    qr_image = qr_image.resize((qr_len, qr_len))
    media_top = 1240
    photo_size = 440
    media_gap = 95
    group_width = photo_size + media_gap + qr_len
    photo_left = int((image_size - group_width) / 2)
    qr_left = photo_left + photo_size + media_gap
    pil_image.paste(
        qr_image, (qr_left, media_top), qr_image
    )

    add_photo_frame(pil_image, imagefilename, photo_left, media_top - 10, photo_size)

    label_font = ImageFont.truetype(font_path, 24)
    draw_centered_text(
        draw,
        photo_left + photo_size / 2,
        media_top - 38,
        "Honorees",
        label_font,
        (232, 239, 255, 205),
    )
    draw_centered_text(
        draw,
        qr_left + qr_len / 2,
        media_top - 38,
        "Verification QR",
        label_font,
        (232, 239, 255, 205),
    )

    footer_y = 1688
    draw_centered_block(
        draw,
        image_size / 2,
        footer_y,
        "Cryptographically signed by Code Collective",
        font_path,
        (232, 239, 255, 215),
        max_width=image_size * 0.62,
        max_height=44,
        start_size=24,
        min_size=18,
        line_spacing_ratio=0.08,
    )
    draw_centered_block(
        draw,
        image_size / 2,
        footer_y + 42,
        "Scan the QR code to verify this certificate",
        font_path,
        (232, 239, 255, 215),
        max_width=image_size * 0.58,
        max_height=40,
        start_size=20,
        min_size=16,
        line_spacing_ratio=0.08,
    )

    # Save the final image
    pil_image.save(output_file, format="WEBP")


    # Upload the image to S3
    bucket_name = "codecollectivecerts"  # Replace with your S3 bucket name
    s3_key = f"{os.path.basename(output_file)}"  # S3 key (path) for the file
    upload_to_s3(output_file, bucket_name,s3_key)
    logging.debug(f"Image uploaded to S3: s3://{bucket_name}/{s3_key}")

    artifact_url = (
        f"https://{bucket_name}.s3.{env.aws_default_region}.amazonaws.com/{s3_key}"
    )
    print(artifact_url)

    logging.debug(f"Badge with text and QR code saved to {output_file}")
    sign_image(output_file)
    logging.debug("Image Signed")

    logging.debug("Updating DB")
    update_dynamodb_table(
        timename=timename, timestamp=timestamp, name=name, table_name=tablename, imageurl=artifact_url
    )
    logging.debug("DB Updated")

    return artifact_url


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: python genAppreciationCert.py <image_path> <full_name> <citation_text>"
        )
        sys.exit(1)

    imagefilename = sys.argv[1]
    if len(sys.argv) < 4:
        print(
            "Usage: python genAppreciationCert.py <image_path> <full_name> <citation_text>"
        )
        sys.exit(1)
    full_name = sys.argv[2]
    citation_text = sys.argv[3]
    table_name = "appreciation"

    generate_badge(imagefilename, full_name, citation_text, table_name)
