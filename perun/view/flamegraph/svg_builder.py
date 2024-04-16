class SVG:
    def __init__(self):
        self.svg = ""

    def header(self, width, height):
        self.svg += f"""<?xml version="1.0" standalone="no"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<svg version="1.1" width="{width}" height="{height}" onload="init(evt)" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
<!-- Flame graph stack visualization. Inspired by Brendan Gregg flamegraph implementation see: -->
<!-- https://github.com/brendangregg/FlameGraph and http://www.brendangregg.com/flamegraphs.html for examples. -->
"""

    def include_style_and_script(self, content):
        self.svg += content

    def group_start(self, attr):
        g_attr = [f'{key}="{value}"' for key, value in attr.items() if key in ['id', 'class']]
        if 'g_extra' in attr:
            g_attr.append(attr['g_extra'])
        if 'href' in attr:
            a_attr = [f'xlink:href="{attr["href"]}"']
            a_attr.append(f'target="{attr.get("target", "_top")}"')
            if 'a_extra' in attr:
                a_attr.append(attr['a_extra'])
            self.svg += f'<a {" ".join(a_attr + g_attr)}>\n'
        else:
            self.svg += f'<g {" ".join(g_attr)}>\n'

        if 'title' in attr:
            self.svg += f'<title>{attr["title"]}</title>\n'

    def group_end(self, attr):
        self.svg += '</a>\n' if 'href' in attr else '</g>\n'

    def filled_rectangle(self, x1, y1, x2, y2, fill, extra=""):
        width = x2 - x1
        height = y2 - y1
        self.svg += f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{width:.1f}" height="{height:.1f}" fill="{fill}" {extra}/>\n'

    def string_ttf(self, id, x, y, string, extra=""):
        id_attr = f'id="{id}" ' if id else ''
        self.svg += f'<text {id_attr}x="{x:.2f}" y="{y}" {extra}>{string}</text>\n'

    def get_svg(self):
        return f"{self.svg}</svg>\n"
