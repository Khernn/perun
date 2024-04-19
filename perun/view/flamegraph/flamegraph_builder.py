import perun.view.flamegraph.svg_builder as svg_builder
import re

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

max_time = 0
time = 0

max_depth = 0

image_width = 1200
frame_height = 16

icicle_graph = 0
stack_reverse = False

node = {}
tmp = {}


def flow(last, this, value, exceptions, delta=None):
    len_a = len(last) - 1
    len_b = len(this) - 1

    i = 0
    len_same = 0
    while i <= len_a and i <= len_b:
        if last[i] != this[i]:
            break
        i += 1
    len_same = i

    for i in range(len_a, len_same - 1, -1):
        key = f"{last[i]};{i}"
        # Retrieve the item once and then use its data
        item_data = tmp.pop(key, {})
        node_entry = node.setdefault(f"{key};{value}", {})
        node_entry['stime'] = item_data.get('stime')
        node_entry['delta'] = item_data.get('delta')
        node_entry['exceptions'] = item_data.get('exceptions')

    for i in range(len_same, len_b + 1):
        key = f"{this[i]};{i}"
        item = tmp.setdefault(key, {})
        item['stime'] = value
        if delta is not None:
            item['delta'] = item.get('delta', 0) + delta
        tmp[key]['exceptions'] = exceptions
        print(exceptions)

    return this


def get_data(profile):
    data = []
    for item in profile:
        item = item.rstrip()
        if stack_reverse:
            # Match the pattern to capture the stack trace and samples
            match = re.match(r'^(.*)\s+(\d+(?:\.\d*)?)\s*(\[[^\]]*\])?$', item)
            if match:
                stack, samples, exceptions = match.groups()
                samples2 = None

                # Check for an additional sample value in the stack trace
                match = re.match(r'^(.*)\s+(\d+(?:\.\d*)?)\s*(\[[^\]]*\])?$', stack)
                if match:
                    stack, samples2, exceptions = match.groups()
                    # Reverse the stack trace for processing and append both samples if there's an additional sample
                    reversed_stack = ';'.join(reversed(stack.split(';')))
                    data.insert(0, f"{reversed_stack} {samples} {samples2} {exceptions}")
                else:
                    # Reverse the stack trace and append the sample
                    reversed_stack = ';'.join(reversed(stack.split(';')))
                    data.insert(0, f"{reversed_stack} {samples} {exceptions}")
            else:
                # Directly insert the line if no matching pattern is found
                data.insert(0, item)
        else:
            data.insert(0, item)

    return data


def process_frames(sorted_data):
    global time
    delta = None
    max_delta = 1
    last = []

    for item in sorted_data:
        item = item.strip()
        match = re.match(r'^(.*)\s+(\d+(?:\.\d*)?)\s*(\[[^\]]*\])?$', item)
        if not match:
            continue
        stack, samples, exceptions = match.groups()
        samples = float(samples)

        print(stack, samples, exceptions)

        samples2 = None
        match = re.match(r'^(.*)\s+(\d+(?:\.\d*)?)\s*(\[[^\]]*\])?$', stack)
        if match:
            stack, samples2 = match.groups()
            samples2 = float(samples2)
            delta = samples2 - samples
            if abs(delta) > max_delta:
                max_delta = abs(delta)
        else:
            delta = None

        last = flow(last, ['', *stack.split(';')], time, exceptions, delta)

        time += samples2 if samples2 is not None else samples

    flow(last, [], time, '[]', delta)


# def check_time(): TODO
#     global time, image_height
#     if not time:
#         svg = svg_builder.SVG()
#         image_height = font_size * 5
#         svg.header(image_width, image_height)
#         svg.string_ttf(None, image_width / 2, font_size * 2)
#         print(svg.get_svg())
#         exit(1)

def todo():
    global time, min_width, node, max_depth, width_per_time

    width_per_time = (image_width - 2 * x_padding) / time
    min_width /= width_per_time

    for id, current_node in node.copy().items():
        func, depth, end_time = id.split(";")
        depth = int(depth)
        end_time = float(end_time)

        start_time = current_node.get('stime')
        if start_time is None:
            raise Exception(f"Missing start for {id}")

        if (end_time - start_time) < min_width:
            del node[id]
            continue

        if depth > max_depth:
            max_depth = depth


def add_js_css(svg):
    include = f'''
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
    		var text = find_child(e, "title").firstChild.nodeValue;
    		return (text)
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

    svg.include_style_and_script(include)


def draw_frames(svg, image_height, count_name):
    frame_padding = 1
    svg.group_start({'id': 'frames'})
    for id, current_node in node.items():
        func, depth, etime = id.split(";")
        depth = int(depth)
        etime = float(etime)
        stime = current_node.get('stime')
        delta = current_node.get('delta', None)

        if func == "" and depth == 0:
            etime = time

        x1 = x_padding + stime * width_per_time
        x2 = x_padding + etime * width_per_time

        if icicle_graph:
            y1 = y_padding_title_included + depth * frame_height
            y2 = y_padding_title_included + (depth + 1) * frame_height - frame_padding
        else:
            y1 = image_height - y_padding_subtitle_included - (depth + 1) * frame_height + frame_padding
            y2 = image_height - y_padding_subtitle_included - depth * frame_height

        samples = int(etime - stime)
        samples_txt = "{:,}".format(samples)

        if func == "" and depth == 0:
            info = f"all ({samples_txt} {count_name}, 100%)"
        else:
            pct = (100 * samples) / (time * 1)
            escaped_func = re.sub(r'[&<>"_]',
                                  lambda x: {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', '_': ''}[x.group()],
                                  func)
            info = f"{escaped_func} ({samples_txt} {count_name}, {pct:.2f}%)"
            if delta is not None:
                d = (-1 * delta) if 0 else delta
                deltapct = (100 * d) / (time * 1)
                info += f", {deltapct:+.2f}%"

        nameattr = {'title': info}
        svg.group_start(nameattr)
        if current_node['exceptions'] != '[]':
            svg.filled_rectangle(x1, y1, x2, y2, 'red', 'rx="2" ry="2"')
        else:
            svg.filled_rectangle(x1, y1, x2, y2, 'green', 'rx="2" ry="2"')
        chars = int((x2 - x1) / (font_size * font_width))
        text = ''

        if chars >= 3:
            text = func[:chars]
            if chars < len(func):
                text = text[:-2] + ".."
            text = re.sub(r'[&<>"_]',
                          lambda x: {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', '_': ''}[x.group()],
                          text)
            svg.string_ttf(None, x1 + 3, 3 + (y1 + y2) / 2, text)
            svg.group_end(nameattr)
    svg.group_end({})


def build_flamegraph(title, count_name):
    global max_depth, frame_height

    image_height = ((max_depth + 1) * frame_height) + y_padding_title_included + y_padding_subtitle_included

    svg = svg_builder.SVG()
    svg.header(image_width, image_height)

    add_js_css(svg)

    svg.filled_rectangle(0, 0, image_width, image_height, 'white')
    svg.string_ttf('title', image_width / 2, font_size * 2, title)
    svg.string_ttf('subtitle', image_width / 2, font_size * 4, "")
    svg.string_ttf("details", x_padding, image_height - (y_padding_subtitle_included / 2), " ")
    svg.string_ttf("unzoom", x_padding, font_size * 2, "Reset Zoom", 'class="hide"')
    svg.string_ttf("search", image_width - x_padding - 100, font_size * 2, "Search")
    svg.string_ttf("ignorecase", image_width - x_padding - 16, font_size * 2, "ic")
    svg.string_ttf("matched", image_width - x_padding - 100, image_height - (y_padding_subtitle_included / 2), " ")

    draw_frames(svg, image_height, count_name)

    return svg.get_svg()


def prepare_resources(profile, title, count_name, width, height, reverse):
    global image_width, frame_height, stack_reverse
    image_width, frame_height, stack_reverse = width, height, reverse
    data = get_data(profile)
    process_frames(sorted(data))
    todo()

    return build_flamegraph(title, count_name)