import io
from PIL import Image
from .security import fail


def validate_media(content, media_type):
    if media_type.startswith('image/'):
        try:
            Image.MAX_IMAGE_PIXELS = 20000000
            with Image.open(io.BytesIO(content)) as image:
                if image.width * image.height > 20000000 or image.format not in ('PNG', 'JPEG'):
                    raise ValueError()
                image.verify()
        except Exception:
            fail('IMAGE_INVALID', 'Use a valid PNG/JPEG under 20 megapixels.', 422)
    elif media_type == 'application/pdf' and not content.startswith(b'%PDF-'):
        fail('PDF_INVALID', 'File is not a PDF.', 422)
    elif media_type.startswith('audio/'):
        valid = content.startswith((b'OggS', b'RIFF', b'ID3', b'\xff', b'\x1aE\xdf\xa3')) or content[4:8] == b'ftyp'
        if not valid:
            fail('AUDIO_INVALID', 'Unrecognized audio container.', 422)


def pdf_text(content):
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(content), strict=True)
    if reader.is_encrypted or len(reader.pages) > 30:
        raise ValueError('PDF must be unencrypted and at most 30 pages')
    pages = []
    for index, page in enumerate(reader.pages):
        # Refuse unusually large decompressed content before text interpretation.
        contents = page.get_contents()
        if contents and len(contents.get_data()) > 5 * 1024 * 1024:
            raise ValueError('PDF page is too complex')
        pages.append({'page': index + 1, 'text': (page.extract_text() or '')[:15000]})
    return pages
