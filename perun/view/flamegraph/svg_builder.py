import re
from typing import List, Tuple

class SVG:
    """
    A class to construct and manage SVG content dynamically.
    Inspired by Brendan Gregg flamegraph implementation see:
    https://github.com/brendangregg/FlameGraph.
    """
    def __init__(self):
        self.svg_content = ""

    def add_header(self, width: int, height: int) -> None:
        """
        Create SVG header with predefined namespace declarations and a doctype.

        Args:
            width (int): The width of the SVG canvas.
            height (int): The height of the SVG canvas.
        """
        header_content = f"""<?xml version="1.0" standalone="no"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<svg version="1.1" width="{width}" height="{height}" onload="init(evt)" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
<!-- Flame graph stack visualization. Inspired by Brendan Gregg flamegraph implementation see: -->
<!-- https://github.com/brendangregg/FlameGraph. -->
"""
        self.svg_content += header_content

    def add_styles(self, content: str) -> None:
        """
        Appends CSS styles directly to the SVG content.

        Args:
            content (str): A string containing style definitions.
        """
        self.svg_content += content

    def start_group(self, attributes: dict) -> None:
        """
        Starts an SVG group element (<g>) or a link element (<a>) if hyperlink attributes are present.

        Args:
            attributes (dict): A dictionary of attributes for the group or link element.
        """
        formatted_attributes = self.format_attributes(attributes, allowed_keys=['id', 'class'])
        extra_tag = self.handle_optional_links(attributes)
        self.svg_content += f'<{extra_tag} {formatted_attributes}>\n'
        self.include_optional_content(attributes)

    def end_group(self, attributes: dict) -> None:
        """
        Closes an SVG group or a link element.

        Args:
            attributes (dict): A dictionary of attributes which may indicate the element type to close.
        """
        tag = 'a' if 'href' in attributes else 'g'
        self.svg_content += f'</{tag}>\n'

    def add_rectangle(self, x1: float, y1: float, x2: float, y2: float, fill: str, extra: str = "") -> None:
        """
        Adds a rectangle element to the SVG.

        Args:
            x1 (float): The x-coordinate of the rectangle's top-left corner.
            y1 (float): The y-coordinate of the rectangle's top-left corner.
            x2 (float): The x-coordinate of the rectangle's bottom-right corner.
            y2 (float): The y-coordinate of the rectangle's bottom-right corner.
            fill (str): The fill color of the rectangle.
            extra (str): Additional attributes.
        """
        width = x2 - x1
        height = y2 - y1
        self.svg_content += f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{width:.1f}" height="{height:.1f}" fill="{fill}" {extra}/>\n'

    def add_text(self, element_id: str, x: float, y: float, string: str, extra: str = "") -> None:
        """
        Adds a text element to the SVG.

        Args:
            element_id (str): An optional ID for the text element.
            x (float): The x-coordinate for the text placement.
            y (float): The y-coordinate for the text baseline.
            string (str): The text string to display.
            extra (str): Additional attributes as a string.
        """
        id_attr = f'id="{element_id}" ' if element_id else ''
        self.svg_content += f'<text {id_attr}x="{x:.2f}" y="{y}" {extra}>{string}</text>\n'

    def get_svg(self) -> str:
        """
        Returns the complete SVG content with the closing tag.

        Returns:
            str: The complete SVG content as a string.
        """
        return f"{self.svg_content}</svg>\n"

    def format_attributes(self, attributes: dict, allowed_keys: list) -> str:
        """
        Formats and returns a string of SVG tag attributes filtered by allowed keys.

        Args:
            attributes (dict): A dictionary of all possible attributes.
            allowed_keys (list): A list of keys that are allowed to be included in the output.

        Returns:
            str: A string of formatted SVG attributes suitable for direct inclusion in an SVG tag.
        """
        return " ".join([f'{key}="{value}"' for key, value in attributes.items() if key in allowed_keys])

    def handle_optional_links(self, attributes: dict) -> str:
        """
        Determines the appropriate SVG tag ('a' for links or 'g' for groups) and formats the link-specific attributes if present.

        Args:
            attributes (dict): A dictionary of attributes which may contain hyperlink attributes.

        Returns:
            str: The tag name ('a' or 'g') followed by formatted link attributes if applicable.
        """
        if 'href' in attributes:
            link_attrs = [f'xlink:href="{attributes["href"]}"', f'target="{attributes.get("target", "_top")}"']
            if 'a_extra' in attributes:
                link_attrs.append(attributes['a_extra'])
            return 'a ' + " ".join(link_attrs)
        return 'g'

    def include_optional_content(self, attributes: dict) -> None:
        """
        Includes optional SVG content such as titles or exceptions within a tag, based on the attributes provided.

        Args:
            attributes (dict): A dictionary containing optional content attributes like 'title' or 'exception'.
        """
        if 'title' in attributes:
            self.svg_content += f'<title>{attributes["title"]}</title>\n'
        if 'exception' in attributes:
            self.svg_content += f'<exception>{attributes["exception"]}</exception>\n'


font_type = 'Verdana'
font_size = 12
font_width = 0.59

min_width = 0.1  # min function width, pixels or percentage of time
width_per_time = 0

name_type = 'Function:'

x_padding = 10
y_padding_title_included = font_size * 3
y_padding_labels_included = font_size * 2 + 10
y_padding_subtitle_included = font_size * 2
y_padding_legend = font_size * 2 + 10

max_time = 0
time = 0

max_depth = 0

image_width = 1200
frame_height = 16

icicle_graph = 0
stack_reverse = False

nodes = {}
temp_storage = {}


def add_styles_and_scripts(svg: str) -> str:
    """
    Appends CSS styles and JavaScript scripts to the provided SVG content.

    This function enhances the visual and interactive features of the SVG by injecting CSS for styling
    and JavaScript for interactivity.

    Args:
        svg (str): A string containing the SVG content to be enhanced.

    Returns:
        str: The SVG content updated with additional style and script tags.
    """
    styles_and_scripts = f'''
<defs >
    <linearGradient id="background" y1="0" y2="1" x1="0" x2="0" >
        <stop stop-color="#e0e0ff" offset="5%" />
        <stop stop-color="#ffffff" offset="95%" />
    </linearGradient>
    <linearGradient id="legend" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" style="stop-color:rgb(255,255,255); stop-opacity:1" />
        <stop offset="100%" style="stop-color:rgb(255,255,0); stop-opacity:1" />
    </linearGradient>
</defs>
<style type="text/css">
    text {{ font-family:{font_type}; font-size:{font_size}px; fill:#000000; }}
    #search, #ignorecase {{ opacity:0.1; cursor:pointer; }}
    #search:hover, #search.show, #ignorecase:hover, #ignorecase.show {{ opacity:1; }}
    #subtitle {{ text-anchor:middle; font-color:#A0A0A0; }}
    #title {{ text-anchor:middle; font-size:{font_size + 5}px}}
    #unzoom {{ cursor:pointer; }}
    #frames > *:hover {{ stroke:black; stroke-width:0.5; cursor:pointer; }}
    .hide {{ display:none; }}
    .parent {{ opacity:0.5; }}
</style>
<script type="text/ecmascript">
<![CDATA[
    "use strict";
    var details, searchbtn, unzoombtn, matchedtxt, svg, searching, currentSearchTerm, ignorecase, ignorecaseBtn;
    function init(evt) {{
        details = document.getElementById("details").firstChild;
        searchbtn = document.getElementById("search");
        ignorecaseBtn = document.getElementById("ignorecase");
        unzoombtn = document.getElementById("unzoom");
        matchedtxt = document.getElementById("matched");
        svg = document.getElementsByTagName("svg")[0];
        searching = 0;
        currentSearchTerm = null;

        // use GET parameters to restore a flamegraphs state.
        var params = get_params();
        if (params.x && params.y)
            zoom(find_group(document.querySelector('[x="' + params.x + '"][y="' + params.y + '"]')));
                if (params.s) search(params.s);
    }}

    // event listeners
    window.addEventListener("click", function(e) {{
        var target = find_group(e.target);
        if (target) {{
            if (target.nodeName == "a") {{
                if (e.ctrlKey === false) return;
                e.preventDefault();
            }}
            if (target.classList.contains("parent")) unzoom(true);
            zoom(target);
            if (!document.querySelector('.parent')) {{
                // we have basically done a clearzoom so clear the url
                var params = get_params();
                if (params.x) delete params.x;
                if (params.y) delete params.y;
                history.replaceState(null, null, parse_params(params));
                unzoombtn.classList.add("hide");
                return;
            }}

            // set parameters for zoom state
            var el = target.querySelector("rect");
            if (el && el.attributes && el.attributes.y && el.attributes._orig_x) {{
                var params = get_params()
                params.x = el.attributes._orig_x.value;
                params.y = el.attributes.y.value;
                history.replaceState(null, null, parse_params(params));
            }}
        }}
        else if (e.target.id == "unzoom") clearzoom();
        else if (e.target.id == "search") search_prompt();
        else if (e.target.id == "ignorecase") toggle_ignorecase();
    }}, false)

    // mouse-over for info
    // show
    window.addEventListener("mouseover", function(e) {{
        var target = find_group(e.target);
        if (target) details.nodeValue = "{name_type} " + g_to_text(target);
    }}, false)

    // clear
    window.addEventListener("mouseout", function(e) {{
        var target = find_group(e.target);
        if (target) details.nodeValue = ' ';
    }}, false)

    // ctrl-F for search
    // ctrl-I to toggle case-sensitive search
    window.addEventListener("keydown",function (e) {{
        if (e.keyCode === 114 || (e.ctrlKey && e.keyCode === 70)) {{
            e.preventDefault();
            search_prompt();
        }}
        else if (e.ctrlKey && e.keyCode === 73) {{
            e.preventDefault();
            toggle_ignorecase();
        }}
    }}, false)

    // functions
    function get_params() {{
        var params = {{}};
        var paramsarr = window.location.search.substr(1).split('&');
        for (var i = 0; i < paramsarr.length; ++i) {{
            var tmp = paramsarr[i].split("=");
            if (!tmp[0] || !tmp[1]) continue;
            params[tmp[0]]  = decodeURIComponent(tmp[1]);
        }}
        return params;
    }}

    function parse_params(params) {{
        var uri = "?";
        for (var key in params) {{
            uri += key + '=' + encodeURIComponent(params[key]) + '&';
        }}
        if (uri.slice(-1) == "&")
            uri = uri.substring(0, uri.length - 1);
        if (uri == '?')
            uri = window.location.href.split('?')[0];
        return uri;
    }}

    function find_child(node, selector) {{
        var children = node.querySelectorAll(selector);
        if (children.length) return children[0];
    }}

    function find_group(node) {{
        var parent = node.parentElement;
        if (!parent) return;
        if (parent.id == "frames") return node;
        return find_group(parent);
    }}

    function orig_save(e, attr, val) {{
        if (e.attributes["_orig_" + attr] != undefined) return;
        if (e.attributes[attr] == undefined) return;
        if (val == undefined) val = e.attributes[attr].value;
        e.setAttribute("_orig_" + attr, val);
    }}

    function orig_load(e, attr) {{
        if (e.attributes["_orig_"+attr] == undefined) return;
        e.attributes[attr].value = e.attributes["_orig_" + attr].value;
        e.removeAttribute("_orig_"+attr);
    }}

    function g_to_text(e) {{
        var title = find_child(e, "title").firstChild.nodeValue;
        var exception = find_child(e, "exception").firstChild.nodeValue;
        return (title + ' Exception:' + exception);
    }}

    function g_to_func(e) {{
        var func = g_to_text(e);
        // if there's any manipulation we want to do to the function
        // name before it's searched, do it here before returning.
        return (func);
    }}

    function update_text(e) {{
        var r = find_child(e, "rect");
        var t = find_child(e, "text");
        var w = parseFloat(r.attributes.width.value) -3;
        var txt = find_child(e, "title").textContent.replace(/\\([^(]*\\)\$/,"");
        t.attributes.x.value = parseFloat(r.attributes.x.value) + 3;

        // Smaller than this size won't fit anything
        if (w < 2 * {font_size} * {font_width}) {{
            t.textContent = "";
            return;
        }}

        t.textContent = txt;
        var sl = t.getSubStringLength(0, txt.length);
        // check if only whitespace or if we can fit the entire string into width w
        if (/^ *\$/.test(txt) || sl < w)
            return;

        // this isn't perfect, but gives a good starting point
        // and avoids calling getSubStringLength too often
        var start = Math.floor((w/sl) * txt.length);
        for (var x = start; x > 0; x = x-2) {{
            if (t.getSubStringLength(0, x + 2) <= w) {{
                t.textContent = txt.substring(0, x) + "..";
                return;
            }}
        }}
        t.textContent = "";
    }}

    // zoom
    function zoom_reset(e) {{
        if (e.attributes != undefined) {{
            orig_load(e, "x");
            orig_load(e, "width");
        }}
        if (e.childNodes == undefined) return;
        for (var i = 0, c = e.childNodes; i < c.length; i++) {{
            zoom_reset(c[i]);
        }}
    }}

    function zoom_child(e, x, ratio) {{
        if (e.attributes != undefined) {{
            if (e.attributes.x != undefined) {{
                orig_save(e, "x");
                e.attributes.x.value = (parseFloat(e.attributes.x.value) - x - {x_padding}) * ratio + {x_padding};
                if (e.tagName == "text")
                    e.attributes.x.value = find_child(e.parentNode, "rect[x]").attributes.x.value + 3;
            }}
            if (e.attributes.width != undefined) {{
                orig_save(e, "width");
                e.attributes.width.value = parseFloat(e.attributes.width.value) * ratio;
            }}
        }}

        if (e.childNodes == undefined) return;
        for (var i = 0, c = e.childNodes; i < c.length; i++) {{
            zoom_child(c[i], x - {x_padding}, ratio);
        }}
    }}

    function zoom_parent(e) {{
        if (e.attributes) {{
            if (e.attributes.x != undefined) {{
                orig_save(e, "x");
                e.attributes.x.value = {x_padding};
            }}
            if (e.attributes.width != undefined) {{
                orig_save(e, "width");
                e.attributes.width.value = parseInt(svg.width.baseVal.value) - ({x_padding} * 2);
            }}
        }}
        if (e.childNodes == undefined) return;
        for (var i = 0, c = e.childNodes; i < c.length; i++) {{
            zoom_parent(c[i]);
        }}
    }}

    function zoom(node) {{
        var attr = find_child(node, "rect").attributes;
        var width = parseFloat(attr.width.value);
        var xmin = parseFloat(attr.x.value);
        var xmax = parseFloat(xmin + width);
        var ymin = parseFloat(attr.y.value);
        var ratio = (svg.width.baseVal.value - 2 * {x_padding}) / width;

        // XXX: Workaround for JavaScript float issues (fix me)
        var fudge = 0.0001;

        unzoombtn.classList.remove("hide");

        var el = document.getElementById("frames").children;
        for (var i = 0; i < el.length; i++) {{
            var e = el[i];
            var a = find_child(e, "rect").attributes;
            var ex = parseFloat(a.x.value);
            var ew = parseFloat(a.width.value);
            var upstack;
            // Is it an ancestor
            if ({icicle_graph} == 0) {{
                upstack = parseFloat(a.y.value) > ymin;
            }} else {{
                upstack = parseFloat(a.y.value) < ymin;
            }}
            if (upstack) {{
                // Direct ancestor
                if (ex <= xmin && (ex+ew+fudge) >= xmax) {{
                    e.classList.add("parent");
                    zoom_parent(e);
                    update_text(e);
                }}
                // not in current path
                else
                    e.classList.add("hide");
            }}
            // Children maybe
            else {{
                // no common path
                if (ex < xmin || ex + fudge >= xmax) {{
                    e.classList.add("hide");
                }}
                else {{
                    zoom_child(e, xmin, ratio);
                    update_text(e);
                }}
            }}
        }}
        search();
    }}

    function unzoom(dont_update_text) {{
        unzoombtn.classList.add("hide");
        var el = document.getElementById("frames").children;
        for(var i = 0; i < el.length; i++) {{
            el[i].classList.remove("parent");
            el[i].classList.remove("hide");
            zoom_reset(el[i]);
            if(!dont_update_text) update_text(el[i]);
        }}
        search();
    }}

    function clearzoom() {{
        unzoom();

        // remove zoom state
        var params = get_params();
        if (params.x) delete params.x;
        if (params.y) delete params.y;
        history.replaceState(null, null, parse_params(params));
    }}

    // search
    function toggle_ignorecase() {{
        ignorecase = !ignorecase;
        if (ignorecase) {{
            ignorecaseBtn.classList.add("show");
        }} else {{
            ignorecaseBtn.classList.remove("show");
        }}
        reset_search();
        search();
    }}

    function reset_search() {{
        var el = document.querySelectorAll("#frames rect");
        for (var i = 0; i < el.length; i++) {{
            orig_load(el[i], "fill")
        }}
        var params = get_params();
        delete params.s;
        history.replaceState(null, null, parse_params(params));
    }}

    function search_prompt() {{
        if (!searching) {{
            var term = prompt("Enter a search term (regexp " +
                "allowed, eg: ^ext4_)"
                + (ignorecase ? ", ignoring case" : "")
                + "\\nPress Ctrl-i to toggle case sensitivity", "");
            if (term != null) search(term);
        }} else {{
            reset_search();
            searching = 0;
            currentSearchTerm = null;
            searchbtn.classList.remove("show");
            searchbtn.firstChild.nodeValue = "Search"
            matchedtxt.classList.add("hide");
            matchedtxt.firstChild.nodeValue = ""
        }}
    }}

    function search(term) {{
        if (term) currentSearchTerm = term;

        var re = new RegExp(currentSearchTerm, ignorecase ? 'i' : '');
        var el = document.getElementById("frames").children;
        var matches = new Object();
        var maxwidth = 0;
        for (var i = 0; i < el.length; i++) {{
            var e = el[i];
            var func = g_to_func(e);
            var rect = find_child(e, "rect");
            if (func == null || rect == null)
                continue;

            // Save max width. Only works as we have a root frame
            var w = parseFloat(rect.attributes.width.value);
            if (w > maxwidth)
                maxwidth = w;

            if (func.match(re)) {{
                // highlight
                var x = parseFloat(rect.attributes.x.value);
                orig_save(rect, "fill");
                rect.attributes.fill.value = "#5296FF";

                // remember matches
                if (matches[x] == undefined) {{
                    matches[x] = w;
                }} else {{
                    if (w > matches[x]) {{
                        // overwrite with parent
                        matches[x] = w;
                    }}
                }}
                searching = 1;
            }}
        }}
        if (!searching)
            return;
        var params = get_params();
        params.s = currentSearchTerm;
        history.replaceState(null, null, parse_params(params));

        searchbtn.classList.add("show");
        searchbtn.firstChild.nodeValue = "Reset Search";

        // calculate percent matched, excluding vertical overlap
        var count = 0;
        var lastx = -1;
        var lastw = 0;
        var keys = Array();
        for (k in matches) {{
            if (matches.hasOwnProperty(k))
                keys.push(k);
        }}
        // sort the matched frames by their x location
        // ascending, then width descending
        keys.sort(function(a, b){{
            return a - b;
        }});
        // Step through frames saving only the biggest bottom-up frames
        // thanks to the sort order. This relies on the tree property
        // where children are always smaller than their parents.
        var fudge = 0.0001;	// JavaScript floating point
        for (var k in keys) {{
            var x = parseFloat(keys[k]);
            var w = matches[keys[k]];
            if (x >= lastx + lastw - fudge) {{
                count += w;
                lastx = x;
                lastw = w;
            }}
        }}
        // display matched percent
        matchedtxt.classList.remove("hide");
        var pct = 100 * count / maxwidth;
        if (pct != 100) pct = pct.toFixed(1)
        matchedtxt.firstChild.nodeValue = "Matched: " + pct + "%";
    }}
]]>
</script>
'''

    svg.add_styles(styles_and_scripts)


def aggregate_stack_data(last_stack: List[str], current_stack: List[str], value: float, ncalls: int, exceptions: List[str]) -> List[str]:
    """
    Aggregates stack trace data by comparing the last and current stack traces to determine divergences and update node information accordingly.

    Args:
        last_stack (List[str]): The previous stack trace as a list of function identifiers.
        current_stack (List[str]): The current stack trace as a list of function identifiers.
        value (float): Function call duration in seconds.
        ncalls (int): The number of calls current function.
        exceptions (List[str]): Any exceptions associated with the current function.

    Returns:
        List[str]: The updated current stack trace.
    """
    # Calculate the length of last and current stack traces
    last_length = len(last_stack) - 1
    current_length = len(current_stack) - 1

    # Find the point where last and current stacks diverge
    common_length = 0
    while common_length <= last_length and common_length <= current_length:
        if last_stack[common_length] != current_stack[common_length]:
            break
        common_length += 1

    # Remove nodes from the end of the last stack to the point of divergence
    for index in range(last_length, common_length - 1, -1):
        key = f"{last_stack[index]};{index}"
        item_data = temp_storage.pop(key, {})
        node_entry = nodes.setdefault(f"{key};{value}", {})
        node_entry['stime'] = item_data.get('stime')
        node_entry['exceptions'] = item_data.get('exceptions')
        node_entry['ncalls'] = item_data.get('ncalls')

    # Add new nodes from the point of divergence to the end of the current stack
    for index in range(common_length, current_length + 1):
        key = f"{current_stack[index]};{index}"
        item = temp_storage.setdefault(key, {})
        item['stime'] = value
        item['exceptions'] = exceptions
        item['ncalls'] = ncalls

    return current_stack


def get_data(profile: List[str]) -> List[str]:
    """
    Processes a list of strings representing profiling data entries and optionally reverses the stack traces.

    Args:
        profile (List[str]): A list of strings, where each string contains data from profiling.

    Returns:
        List[str]: A list containing processed data entries.

    """
    data = []
    for item in profile:
        item = item.rstrip()
        parts = item.split()
        if len(parts) >= 4:
            stack, samples, ncalls, exceptions = parts[0], float(parts[1]), int(parts[2]), ' '.join(parts[3:])
            if stack_reverse:
                # Reverse the stack trace for processing
                reversed_stack = ';'.join(reversed(stack.split(';')))
                data.append(f"{reversed_stack} {samples} {ncalls} {exceptions}")
            else:
                data.append(item)
        else:
            # Append the line directly if it does not meet expected formatting
            data.append(item)

    if stack_reverse:
        data.reverse()

    return data


def process_frames(sorted_data: List[str]) -> None:
    """
    Processes each frame from sorted profiling data, updating global execution time and aggregating data.

    Args:
        sorted_data (List[str]): A stack trace.
    """
    global time
    last = []

    for item in sorted_data:
        item = item.strip()
        parts = item.split()
        if len(parts) < 4:
            continue
        stack, exclusive_time, ncalls, exceptions = parts[0], float(parts[1]), int(parts[2]), ' '.join(parts[3:])

        last = aggregate_stack_data(last, ['', *stack.split(';')], time, ncalls, exceptions)
        time += exclusive_time

    aggregate_stack_data(last, [], time, 0, '[]')  # Final call to process any remaining data


def calculate_depth_and_frames_width() -> None:
    """
    Calculates the display width for each function unit and filters out nodes below a visibility threshold.

    Raises:
        ValueError: If a node is found without a start time, indicating incomplete or corrupted data.
    """
    global time, min_width, nodes, max_depth, width_per_time

    # Calculate the width of each time unit based on the current settings
    width_per_time = (image_width - 2 * x_padding) / time
    min_width /= width_per_time

    to_delete = []  # List to store nodes to delete
    for node_id, current_node in nodes.items():
        func, depth_str, end_time_str = node_id.split(";")
        depth = int(depth_str)
        end_time = float(end_time_str)

        start_time = current_node.get('stime')
        if start_time is None:
            raise ValueError(f"Missing start time for node '{node_id}'")

        # Only consider nodes whose active time is above the minimum width threshold
        if (end_time - start_time) < min_width:
            to_delete.append(node_id)
        else:
            if depth > max_depth:
                max_depth = depth

    # Remove nodes that are too narrow to be displayed
    for node_id in to_delete:
        del nodes[node_id]


def get_color(function_calls: int, total_calls: int) -> str:
    """
    Generates an RGB color string with varying shades of yellow based on the ratio of function calls to total calls.

    Args:
        function_calls (int): The number of calls for a particular function.
        total_calls (int): The total number of calls across all functions.

    Returns:
        str: An RGB string representing the color.

    Raises:
        ValueError: If total_calls is zero to prevent division by zero errors.
    """
    if total_calls == 0:
        raise ValueError("total_calls cannot be zero to prevent division by zero")

    ratio = function_calls / total_calls
    blue = (1 - ratio) * 255
    return f"rgb(255, 255, {int(blue)})"


def escape_html(text: str) -> str:
    """
    Escapes HTML special characters in text.

    Args:
        text (str): The text to be escaped.

    Returns:
        str: The escaped text with HTML special characters converted to HTML entities.
    """
    return re.sub(r'[&<>"_]',
                  lambda x: {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', '_': ''}[x.group()],
                  text)


def calculate_frame_position(depth: int, time_offset: Tuple[float, float], image_height: int, frame_padding: int) -> Tuple[float, float, float, float]:
    """
    Calculates the position of a frame in the visualization.

    Args:
        depth (int): The depth of the frame in the call stack.
        time_offset (Tuple[float, float]): A tuple representing the start and end time offsets of the frame.
        image_height (int): The total height of the image.
        frame_padding (int): The padding between frames at the same depth.

    Returns:
        Tuple[float, float, float, float]: The coordinates (x1, x2, y1, y2) of the frame.
    """
    x1 = x_padding + time_offset[0] * width_per_time
    x2 = x_padding + time_offset[1] * width_per_time
    if icicle_graph:
        y1 = y_padding_title_included + depth * frame_height
        y2 = y_padding_title_included + (depth + 1) * frame_height - frame_padding
    else:
        y1 = image_height - y_padding_subtitle_included - (depth + 1) * frame_height + frame_padding
        y2 = image_height - y_padding_subtitle_included - depth * frame_height
    return x1, x2, y1, y2


def draw_frames(svg: SVG, image_height: int, calls: int) -> None:
    """
    Draws frames representing function calls on an SVG canvas.

    Args:
        svg (SVG): An instance of an SVG class responsible for SVG generation.
        image_height (int): The total height of the SVG image.
        calls (int): The total number of function calls, used for color calculation.

    This function iterates through call stack,
    calculates each function position, and draws it within an SVG group.

    Each frame is represented as a rectangle with optional text. Frames are colored differently based
    on whether they contain exceptions or based on the volume of calls.
    """
    frame_padding = 1
    svg.start_group({'id': 'frames'})

    for node_id, node in nodes.items():
        func, depth_str, etime_str = node_id.split(";")
        depth, etime = int(depth_str), float(etime_str)
        stime = node.get('stime')
        time_offset = (stime, etime if func != "" or depth > 0 else time)

        x1, x2, y1, y2 = calculate_frame_position(depth, time_offset, image_height, frame_padding)

        info = format_node_info(func, time, etime, stime, depth)
        svg.start_group({'title': info, 'exception': node['exceptions']})

        color = '#969600' if func == "" else ('pink' if node['exceptions'] != '[]' else get_color(node["ncalls"], calls))
        svg.add_rectangle(x1, y1, x2, y2, color, 'rx="2" ry="2"')

        display_text = truncate_text(func, x2 - x1)
        svg.add_text(None, x1 + 3, 3 + (y1 + y2) / 2, escape_html(display_text))

        svg.end_group({'title': info, 'exception': node['exceptions']})
    svg.end_group({})


def truncate_text(func_name: str, width: float) -> str:
    """
    Truncates a function name to fit within a specified width.

    Args:
        func_name (str): The function name to be truncated.
        width (float): The available width in pixels.

    Returns:
        str: The truncated function name.
    """
    max_chars = int(width / (font_size * font_width))
    if max_chars < 3:
        return ""  # Not enough space for any meaningful text
    if len(func_name) > max_chars:
        return func_name[:max_chars - 2] + ".."  # Subtract 2 to fit the ellipsis
    return func_name  # Return the original name if it fits


def format_time_units(time_elapsed: float) -> str:
    """
    Formats a time duration into a readable string with appropriate units.

    Args:
        time_elapsed (float): The time duration in seconds.

    Returns:
        str: A string representation of the time duration with units adjusted to seconds, milliseconds, microseconds, or nanoseconds.
    """
    if time_elapsed >= 1:  # More than 1 second
        return f"{time_elapsed:.2f} seconds"
    elif time_elapsed >= 0.001:  # More than 1 millisecond
        return f"{time_elapsed * 1000:.2f} milliseconds"
    elif time_elapsed >= 0.000001:  # More than 1 microsecond
        return f"{time_elapsed * 1000000:.2f} microseconds"
    else:  # Less than 1 microsecond, show in nanoseconds
        return f"{time_elapsed * 1000000000:.2f} nanoseconds"


def format_node_info(func: str, total_time: float, etime: float, stime: float, depth: int) -> str:
    """
    Generates a formatted string describing a node's information.

    Args:
        func (str): The function's name.
        total_time (float): The total time recorded in the profiling.
        etime (float): The end time of the function call.
        stime (float): The start time of the function call.
        depth (int): The depth of the function in the call stack.

    Returns:
        str: A formatted string containing the function's name, time elapsed, and its percentage of the total time.
    """
    time_elapsed = etime - stime
    samples_txt = format_time_units(time_elapsed)
    if func == "" and depth == 0:
        return f"all ({samples_txt}, 100%)"
    pct = (100 * time_elapsed) / total_time
    return f"{escape_html(func)} ({samples_txt}, {pct:.2f}%)"


def build_flamegraph(title: str, calls: int) -> str:
    """
    Constructs an SVG-based flame graph for visualizing function calls.

    Args:
        title (str): The title to display at the top of the flame graph.
        calls (int): The total number of functions calls to be visualized.

    Returns:
        str: An SVG string representing the complete flame graph visualization.

    This function sets up the flame graph's dimensions based on the maximum depth of the call stack
    and additional padding for titles and subtitles. It initializes the SVG, adds styles, scripts,
    and constructs the various text and rectangle elements that make up the flame graph.
    """
    global max_depth, frame_height

    image_height = ((max_depth + 1) * frame_height) + y_padding_title_included + y_padding_subtitle_included + 2 * y_padding_legend

    svg = SVG()
    svg.add_header(image_width, image_height)

    add_styles_and_scripts(svg)

    svg.add_rectangle(0, 0, image_width, image_height, 'url(#background)')
    svg.add_text('title', image_width / 2, font_size * 2, title)
    svg.add_text("details", x_padding, image_height - (y_padding_subtitle_included / 2), " ")
    svg.add_text("unzoom", x_padding, font_size * 2, "Reset Zoom", 'class="hide"')
    svg.add_text("search", image_width - x_padding - 170, font_size * 2, "Search")
    svg.add_text("ignorecase", image_width - x_padding - 70, font_size * 2, "Ignore case")

    svg.add_rectangle(10, y_padding_title_included + font_size * 2, image_width - 10,
                      y_padding_title_included + font_size * 2 + 20, 'url(#legend)',
                      'style="stroke-width:1;stroke:black"')
    svg.add_text("", 10, y_padding_title_included + font_size + 5, "0")
    svg.add_text("", image_width / 2, y_padding_title_included + font_size + 5, "Number of calls")
    svg.add_text("", image_width - (len(str(calls - 1)) * 7) - 10,
                 y_padding_title_included + font_size + 5, f"{calls}")

    svg.add_text("matched", image_width - x_padding - 100, image_height - (y_padding_subtitle_included / 2), " ")

    draw_frames(svg, image_height, calls)

    return svg.get_svg()


def build_svg(profile: List[str], title: str, width: int, height: int, reverse: bool) -> str:
    """
    Constructs an SVG flame graph based on profiling data.

    This function serves as the main entry point to process profiling data and generate a corresponding flame graph.

    Args:
        profile (List[str]): A list of strings representing the profiling data.
        title (str): The title of the flame graph.
        width (int): The width of the SVG canvas.
        height (int): The default height of the SVG canvas.
        reverse (bool): A flag to indicate whether the stack trace should be reversed.

    Returns:
        str: The complete SVG string representing the flame graph.
    """
    global image_width, frame_height, stack_reverse
    image_width, frame_height, stack_reverse = width, height, reverse

    data = get_data(profile)
    process_frames(sorted(data))
    calculate_depth_and_frames_width()

    return build_flamegraph(title, len(profile))
