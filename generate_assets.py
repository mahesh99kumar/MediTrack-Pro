import os
import zlib
import struct

def create_png(filename, width, height, r, g, b):
    # PNG signature
    png_sig = b'\x89PNG\r\n\x1a\n'
    
    # IHDR chunk: width, height, bit_depth=8, color_type=2 (RGB), compression=0, filter=0, interlace=0
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data)
    ihdr_chunk = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)
    
    # Image data: each scanline starts with filter byte 0
    raw_row = b'\x00' + bytes([r, g, b]) * width
    raw_data = raw_row * height
    compressed_data = zlib.compress(raw_data, 9)
    
    idat_crc = zlib.crc32(b'IDAT' + compressed_data)
    idat_chunk = struct.pack('>I', len(compressed_data)) + b'IDAT' + compressed_data + struct.pack('>I', idat_crc)
    
    # IEND chunk
    iend_crc = zlib.crc32(b'IEND')
    iend_chunk = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)
    
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'wb') as f:
        f.write(png_sig + ihdr_chunk + idat_chunk + iend_chunk)

if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.abspath(__file__))
    img_dir = os.path.join(base_dir, 'static', 'images')
    create_png(os.path.join(img_dir, 'logo.png'), 128, 128, 13, 148, 136)
    create_png(os.path.join(img_dir, 'pharmacy.jpg'), 400, 300, 15, 118, 110)
    print("Placeholder images generated successfully in static/images/")
