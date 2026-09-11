"""Exclude text fully concealed by later opaque rectangular paint operations.

Never modify the source PDF. Unsupported shapes, clipped/grouped paint and
partial coverage are kept conservatively; a drawing bbox alone is not a mask.
"""
from collections import defaultdict
import fitz


def _key(code, origin):
    return code, round(origin[0], 3), round(origin[1], 3)


def visible_words(page):
    covers = []
    for drawing in page.get_drawings(extended=True):
        items = drawing.get('items', [])
        if (drawing.get('type') in ('f', 'fs')
                and drawing.get('fill_opacity') == 1
                and not drawing.get('layer')
                and drawing.get('level', 0) == 0
                and len(items) == 1 and items[0][0] == 're'):
            covers.append((drawing['seqno'], fitz.Rect(items[0][1])))
    if not covers:
        return page.get_text('words')

    visibility = defaultdict(list)
    for span in page.get_texttrace():
        later = [rect for seq, rect in covers if seq > span['seqno']]
        for code, glyph, origin, bbox in span['chars']:
            hidden = any(rect.contains(fitz.Rect(bbox)) for rect in later)
            visibility[_key(code, origin)].append(not hidden)

    words = []
    for block in page.get_text('rawdict')['blocks']:
        if block['type'] != 0:
            continue
        for line_index, line in enumerate(block['lines']):
            token = []
            word_index = 0

            def flush():
                nonlocal word_index
                if not token:
                    return
                # Retain unknown or partially visible words without inventing
                # fragments that could be mistaken for a different product SKU.
                if any(any(visibility.get(_key(ord(c['c']), c['origin']), [True]))
                       for c in token):
                    box = fitz.Rect(token[0]['bbox'])
                    for char in token[1:]:
                        box |= fitz.Rect(char['bbox'])
                    words.append((*box, ''.join(c['c'] for c in token),
                                  block['number'], line_index, word_index))
                word_index += 1
                token.clear()

            for span in line['spans']:
                for char in span['chars']:
                    if char['c'].isspace():
                        flush()
                    else:
                        token.append(char)
            flush()
    return words
