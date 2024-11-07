import fontforge
import psMat  # Import the psMat module for transformations

# Load the original font
font_path = "chinese_rocks_rg.otf"
output_path = "chinese_rocks_rg_halfheight.otf"
font = fontforge.open(font_path)

# Compress each glyph vertically by 50%
for glyph in font.glyphs():
    glyph.transform(psMat.scale(1, 0.35))  # Scale X by 100%, Y by 50%

# Save the modified font
font.generate(output_path)
print(f"Saved compressed font to {output_path}")
