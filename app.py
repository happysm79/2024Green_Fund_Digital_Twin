from flask import Flask, request, render_template, jsonify, send_from_directory
import os
import traceback
import pandas as pd
import wntr
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np
import wntr
import matplotlib
matplotlib.use("Agg")
import plotly.graph_objects as go
import json
import matplotlib.animation as animation
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as colors
import numpy as np
import time



app = Flask(__name__)

# Set up directories for uploads and static files
UPLOAD_FOLDER = "uploads"
STATIC_FOLDER = "static"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)

global_inp_file = None  # Store the uploaded file path

def seconds_to_ddhhmm(seconds):
    """Convert seconds to DD:HH:MM format"""
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    return f"{days:02}:{hours:02}:{minutes:02}"

def ddhhmm_to_seconds(ddhhmm, max_seconds):
    """Convert DD:HH:MM format to total seconds"""
    try:
        parts = ddhhmm.split(":")
        if len(parts) == 3:  # If full format is entered
            days, hours, minutes = map(int, parts)
        elif len(parts) == 2:  # If HH:MM is entered (assume 0 days)
            days, hours, minutes = 0, *map(int, parts)
        else:
            return None  # Invalid format

        total_seconds = (days * 86400) + (hours * 3600) + (minutes * 60)

        # If entered time exceeds max simulation time, round to max
        return min(total_seconds, max_seconds)
    
    except ValueError:
        return None  # Handle invalid input


def nearest_time_step(selected_seconds, time_steps):
    """Finds the closest available time step"""
    return min(time_steps, key=lambda x: abs(x - selected_seconds))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_file():
    """Handles file upload from frontend"""
    global global_inp_file
    try:
        if "file" not in request.files:
            print("[ERROR] No file part in request")
            return jsonify({"message": "No file part in request"}), 400

        file = request.files["file"]

        if file.filename == "":
            print("[ERROR] No selected file")
            return jsonify({"message": "No selected file"}), 400

        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        
        # Ensure upload folder is writable
        print(f"[DEBUG] Saving file to: {filepath}")
        
        file.save(filepath)
        global_inp_file = filepath  # Store file path globally

        return jsonify({"message": "File uploaded successfully!", "file_path": filepath}), 200

    except Exception as e:
        print("[ERROR] File Upload Failed:", str(e))
        traceback.print_exc()  # Print full error traceback
        return jsonify({"message": "File upload failed!", "error": str(e)}), 500


def looks_like_latlon(x, y):
    return -90 <= y <= 90 and -180 <= x <= 180

from pyproj import Transformer

@app.route("/get_network", methods=["GET"])
def get_network():
    global global_inp_file
    if not global_inp_file:
        return jsonify({"error": "No file uploaded!"}), 400

    try:
        wn = wntr.network.WaterNetworkModel(global_inp_file)
        nodes, links = [], []
        x_coords, y_coords = [], []

        for node_name in wn.node_name_list:
            node = wn.get_node(node_name)
            if hasattr(node, "coordinates") and node.coordinates:
                x, y = node.coordinates
                x_coords.append(x)
                y_coords.append(y)

        if not x_coords or not y_coords:
            return jsonify({"error": "No valid node coordinates"}), 500

        project = get_projection_function(wn)


        for node_name in wn.node_name_list:
            node = wn.get_node(node_name)
            if node.coordinates:
                lat, lon = project(*node.coordinates)
                nodes.append({"name": node_name, "lat": lat, "lon": lon})

        for link_name in wn.link_name_list:
            link = wn.get_link(link_name)
            start_node = wn.get_node(link.start_node)
            end_node = wn.get_node(link.end_node)
            if start_node.coordinates and end_node.coordinates:
                start_latlon = project(*start_node.coordinates)
                end_latlon = project(*end_node.coordinates)
                links.append({"start": list(start_latlon), "end": list(end_latlon)})

        return jsonify({"nodes": nodes, "links": links})

    except Exception as e:
        print("[ERROR] Failed to load network:", e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500



from pyproj import Transformer

def get_projection_function(wn):
    """Returns a projection function using node coordinates in the WN model"""
    x_coords, y_coords = [], []
    for node_name in wn.node_name_list:
        node = wn.get_node(node_name)
        if hasattr(node, "coordinates") and node.coordinates:
            x, y = node.coordinates
            x_coords.append(x)
            y_coords.append(y)

    if not x_coords or not y_coords:
        raise ValueError("No valid coordinates found in WN model")

    avg_x = sum(x_coords) / len(x_coords)
    avg_y = sum(y_coords) / len(y_coords)

    transformer = Transformer.from_crs("EPSG:32616", "EPSG:4326", always_xy=True)
    LAT_OFFSET = +0.000975
    LON_OFFSET = +0.00280
    SCALE_FACTOR = 0.660

    def project(x, y):
        x_scaled = avg_x + (x - avg_x) * SCALE_FACTOR
        y_scaled = avg_y + (y - avg_y) * SCALE_FACTOR
        lon, lat = transformer.transform(x_scaled, y_scaled)
        return lat + LAT_OFFSET, lon + LON_OFFSET

    return project



# File: app.py (Flask backend)
@app.route("/visualize_data", methods=["POST"])
def visualize_data():
    global global_inp_file
    if not global_inp_file:
        return jsonify({"error": "No input file uploaded!"}), 400

    try:
        data = request.json
        view_type = data["view_type"]
        element_type = data["element_type"]
        parameter = data["parameter"]
        entered_time = data["time_stamp"]

        wn = wntr.network.WaterNetworkModel(global_inp_file)
        wn.options.hydraulic.demand_model = 'PDD'
        sim = wntr.sim.WNTRSimulator(wn)
        results = sim.run_sim()

        max_time = max(results.time)
        selected_seconds = ddhhmm_to_seconds(entered_time, max_time)
        if selected_seconds is None:
            return jsonify({"error": "Invalid time format. Use DD:HH:MM"}), 400

        if view_type == "static":
            time_steps = [nearest_time_step(selected_seconds, results.time)]
        else:
            time_steps = [t for t in results.time if t <= selected_seconds]

        output = {
            "view_type": view_type,
            "element_type": element_type,
            "parameter": parameter,
            "unit": "",
            "frames": []
        }

        if parameter == "unit_head_loss":
            results.link["unit_head_loss"] = compute_unit_head_loss(wn, results)

        transformer = Transformer.from_crs("EPSG:32616", "EPSG:4326", always_xy=True)
        LAT_OFFSET = +0.000975
        LON_OFFSET = +0.00280
        SCALE_FACTOR = 0.660

        # ✅ FIXED unpacking nodes correctly
        valid_nodes = [node for _, node in wn.nodes() if node.coordinates]
        avg_x = np.mean([node.coordinates[0] for node in valid_nodes])
        avg_y = np.mean([node.coordinates[1] for node in valid_nodes])

        def project(x, y):
            x_scaled = avg_x + (x - avg_x) * SCALE_FACTOR
            y_scaled = avg_y + (y - avg_y) * SCALE_FACTOR
            lon, lat = transformer.transform(x_scaled, y_scaled)
            return lat + LAT_OFFSET, lon + LON_OFFSET

        for t in time_steps:
            frame = {"timestamp": seconds_to_ddhhmm(t), "items": []}
            if element_type == "node":
                data_values = results.node[parameter].loc[t, :]
                for name in wn.node_name_list:
                    node = wn.get_node(name)
                    if node.coordinates:
                        lat, lon = project(*node.coordinates)
                        val = round(data_values.get(name, 0), 2)
                        frame["items"].append({
                            "type": "node",
                            "name": name,
                            "lat": lat,
                            "lon": lon,
                            "value": val,
                            "timestamp": seconds_to_ddhhmm(t)
                        })
            else:
                if parameter == "unit_head_loss":
                    data_values = results.link["unit_head_loss"].loc[t, :]
                else:
                    data_values = results.link[parameter].loc[t, :]

                for name in wn.link_name_list:
                    link = wn.get_link(name)
                    start = wn.get_node(link.start_node)
                    end = wn.get_node(link.end_node)
                    if start.coordinates and end.coordinates:
                        lat1, lon1 = project(*start.coordinates)
                        lat2, lon2 = project(*end.coordinates)
                        val = round(data_values.get(name, 0), 2)
                        frame["items"].append({
                            "type": "link",
                            "name": name,
                            "start": [lat1, lon1],
                            "end": [lat2, lon2],
                            "value": val,
                            "timestamp": seconds_to_ddhhmm(t)
                        })

            output["frames"].append(frame)

        return jsonify(output)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def compute_unit_head_loss(wn, results):
    """Compute unit head loss for each pipe."""
    unit_head_loss = pd.DataFrame(index=results.time, columns=wn.pipe_name_list)

    for time in results.time:
        for pipe in wn.pipe_name_list:
            try:
                # Ensure valid data
                if pipe in results.link["flowrate"].columns:
                    flow = results.link["flowrate"].loc[time, pipe]
                else:
                    flow = 0  # Default to zero if missing

                link = wn.get_link(pipe)
                length = link.length if hasattr(link, "length") else 0
                diameter = link.diameter if hasattr(link, "diameter") else 0
                hw_coeff = link.roughness if hasattr(link, "roughness") else 0

                if diameter > 0 and hw_coeff > 0:
                    hl = (10.67 * length * abs(flow) ** 1.85) / (hw_coeff ** 1.85 * diameter ** 4.87)
                else:
                    hl = 0

                unit_head_loss.loc[time, pipe] = hl

            except KeyError:
                unit_head_loss.loc[time, pipe] = None  # Handle missing data

    return unit_head_loss


def compute_unit_head_loss_animated(wn, results):
    """Compute unit head loss for each pipe dynamically for animated visualization."""
    try:
        unit_head_loss = pd.DataFrame(index=results.time, columns=wn.pipe_name_list)

        for time in results.time:
            for pipe in wn.pipe_name_list:
                try:
                    # Ensure valid data
                    if pipe in results.link["flowrate"].columns:
                        flow = results.link["flowrate"].loc[time, pipe]
                    else:
                        flow = 0  # Default to zero if missing

                    link = wn.get_link(pipe)
                    length = link.length if hasattr(link, "length") else 0
                    diameter = link.diameter if hasattr(link, "diameter") else 0
                    hw_coeff = link.roughness if hasattr(link, "roughness") else 0

                    if diameter > 0 and hw_coeff > 0:
                        hl = (10.67 * length * abs(flow) ** 1.85) / (hw_coeff ** 1.85 * diameter ** 4.87)
                    else:
                        hl = 0

                    unit_head_loss.loc[time, pipe] = hl

                except KeyError:
                    unit_head_loss.loc[time, pipe] = None  # Handle missing data

        return unit_head_loss

    except Exception as e:
        print(f"[ERROR] Failed to compute unit head loss for animated visualization: {str(e)}")
        return None


def scale_units(parameter, data):
    """
    Scale values for specific parameters and update unit labels.
    Returns updated data and unit label.
    """
    if parameter in ["demand", "flowrate"]:
        data = data * 1000  # Scale values
        unit = "10³ m³/s"
    elif parameter == "head" or parameter == "pressure" or parameter == "unit_head_loss":
        unit = "m"
    elif parameter == "velocity":
        unit = "m/s"
    else:
        unit = ""

    return data, unit


import plotly.express as px  # ✅ Ensure Plotly is imported
import plotly.graph_objects as go
import plotly.io as pio

def render_static_visualization(results, element_type, parameter, time_step, entered_time):
    """Generates an interactive layout using Plotly for static visualization."""
    try:
        wn = wntr.network.WaterNetworkModel(global_inp_file)

        # ✅ Define units for parameters
        parameter_units = {
            "demand": "10³ m³/s",
            "head": "m",
            "pressure": "m",
            "flowrate": "10³ m³/s",
            "velocity": "m/s",
            "unit_head_loss": "m"
        }

        # ✅ Get unit for selected parameter
        unit = parameter_units.get(parameter, "")

        # ✅ Ensure results.link is properly structured before using
        if not isinstance(results.link, dict):
            results.link = results.link.to_dict()  # Convert DataFrame to dict if needed

        # ✅ Compute unit head loss if required
        if parameter == "unit_head_loss":
            if "unit_head_loss" not in results.link:
                results.link["unit_head_loss"] = compute_unit_head_loss(wn, results)
            data = results.link["unit_head_loss"].loc[time_step, :].round(2)

        # ✅ Fetch relevant data
        if element_type == "node":
            data = results.node[parameter].loc[time_step, :]
        else:
            if parameter == "unit_head_loss":
                if "unit_head_loss" not in results.link:
                    results.link["unit_head_loss"] = compute_unit_head_loss(wn, results)
            data = results.link[parameter].loc[time_step, :]

        # ✅ Round all values to 2 decimal places (for hover + table)
        data = data.apply(lambda x: round(x * 1000, 2) if parameter in ["demand", "flowrate"] else round(x, 2))


        data = data.round(2)
        df = pd.DataFrame(data).T
        df.insert(0, "Time", [seconds_to_ddhhmm(time_step)])
        table_html = df.to_html(index=False, border=1, classes="table table-bordered")

        fig = go.Figure()

        if element_type == "node":
            node_x, node_y, node_values, node_text = [], [], [], []

            for node_name in wn.node_name_list:
                node = wn.get_node(node_name)
                if node_name in data.index:
                    node_x.append(node.coordinates[0])
                    node_y.append(node.coordinates[1])
                    node_values.append(data[node_name])
                    node_text.append(f"Node: {node_name}<br>{parameter.capitalize()} : {data[node_name]} ({unit})")

            fig.add_trace(go.Scatter(
                x=node_x, y=node_y, mode="markers",
                marker=dict(size=6, color=node_values, colorscale="viridis", showscale=True),
                text=node_text, hoverinfo="text",
                showlegend=False  # ✅ Hide legend for nodes
            ))

            # ✅ Draw pipes in black
            for link_name in wn.link_name_list:
                link = wn.get_link(link_name)
                start_node = wn.get_node(link.start_node)
                end_node = wn.get_node(link.end_node)
                fig.add_trace(go.Scatter(
                    x=[start_node.coordinates[0], end_node.coordinates[0]],
                    y=[start_node.coordinates[1], end_node.coordinates[1]],
                    mode="lines",
                    line=dict(color="black", width=1),
                    hoverinfo="skip",  # ✅ No hover text for pipes
                    showlegend=False
                ))

        else:  # ✅ Link-based visualization (Flowrate, Velocity, Unit Head Loss)
            link_x, link_y, link_values, link_text = [], [], [], []

            for link_name in wn.link_name_list:
                link = wn.get_link(link_name)
                start_node = wn.get_node(link.start_node)
                end_node = wn.get_node(link.end_node)

                if link_name in data.index:
                    value = data[link_name]
                    link_x.extend([start_node.coordinates[0], end_node.coordinates[0], None])  # ✅ None breaks the line
                    link_y.extend([start_node.coordinates[1], end_node.coordinates[1], None])
                    link_values.append(value)
                    link_text.append(f"Link: {link_name}<br>{parameter.capitalize()} : {value} ({unit})")

            # ✅ Draw links with colors
            fig.add_trace(go.Scatter(
                x=link_x, y=link_y, mode="lines",
                line=dict(color="blue", width=2),
                text=link_text, hoverinfo="text",
                showlegend=False  # ✅ Hide legend for links
            ))

            # ✅ Add small dots for better visibility of link locations
            fig.add_trace(go.Scatter(
                x=[start_node.coordinates[0] for link_name in wn.link_name_list if link_name in data.index],
                y=[start_node.coordinates[1] for link_name in wn.link_name_list if link_name in data.index],
                mode="markers",
                marker=dict(size=6, color=link_values, colorscale="viridis", showscale=True),
                text=link_text,
                hoverinfo="text",
                showlegend=False
            ))

        # ✅ Ensure title reflects user-entered timestamp and correct units
        fig.update_layout(
            title=f"{parameter.capitalize()} ({unit}) at Time {entered_time}",
            xaxis_title="X",
            yaxis_title="Y",
            plot_bgcolor="rgba(240,240,240,0.9)"
        )

        # ✅ Convert Plotly figure to HTML
        fig_html = fig.to_html(full_html=False)

        return f"""
            <div>{fig_html}</div>
            <br>
            <div style="overflow-x:auto; margin-top:10px;">
                <h3>{parameter.capitalize()} ({unit}) at Time {entered_time}</h3>
                {table_html}
            </div>
        """

    except Exception as e:
        print("[ERROR] Static visualization failed:", str(e))
        return f'<p style="color:red;">[ERROR] {str(e)}</p>'


import plotly.graph_objects as go
import pandas as pd
import wntr
import matplotlib.cm as cm
import matplotlib.colors as mcolors

def render_animated_visualization(results, element_type, parameter, end_time, entered_time):
    """Generates an interactive animated layout for nodes and links with working Plotly Play/Pause buttons."""
    try:
        wn = wntr.network.WaterNetworkModel(global_inp_file)

        # ✅ Define units for parameters
        parameter_units = {
            "demand": "m³/s",
            "head": "m",
            "pressure": "m",
            "flowrate": "m³/s",
            "velocity": "m/s",
            "unit_head_loss": "m"
        }
        unit = parameter_units.get(parameter, "")

        max_time = max(results.time)
        max_time_ddhhmm = seconds_to_ddhhmm(max_time)  # Convert max simulation time

        # ✅ Convert entered time to seconds
        selected_seconds = ddhhmm_to_seconds(entered_time, max_time)
        if selected_seconds is None:
            return '<p style="color:red;">[ERROR] Invalid time format. Use DD:HH:MM</p>'


        # ✅ Find the closest available time step
        frames = [t for t in results.time if t <= selected_seconds]
        total_frames = len(frames)

        if not frames:
            return '<p style="color:red;">[ERROR] No valid time steps available</p>'

        # ✅ Fetch data for all timestamps up to entered timestamp
        if element_type == "node":
            raw_data = results.node[parameter].loc[frames, :]
        else:
            if parameter == "unit_head_loss":
                results.link["unit_head_loss"] = compute_unit_head_loss_animated(wn, results)
            raw_data = results.link[parameter].loc[frames, :]


        data, unit = scale_units(parameter, raw_data)


        # ✅ Convert time steps to DD:HH:MM format
        time_labels = [seconds_to_ddhhmm(t) for t in frames]

        # ✅ Convert data to Pandas DataFrame
        df = pd.DataFrame(data)
        df.insert(0, "Time", time_labels)  # Insert Time column at the beginning

        # ✅ Convert to HTML table
        table_html = df.to_html(index=False, border=1, classes="table table-bordered")

        fig = go.Figure()

        # ✅ NODE LOGIC
        if element_type == "node":
            node_x, node_y, node_names = [], [], []
            adjacency_list = []

            for node_name in wn.node_name_list:
                node = wn.get_node(node_name)
                if hasattr(node, "coordinates") and node.coordinates:
                    node_x.append(node.coordinates[0])
                    node_y.append(node.coordinates[1])
                    node_names.append(node_name)

            for link_name in wn.link_name_list:
                link = wn.get_link(link_name)
                start_node = wn.get_node(link.start_node)
                end_node = wn.get_node(link.end_node)
                if hasattr(start_node, "coordinates") and hasattr(end_node, "coordinates"):
                    adjacency_list.append(
                        ([start_node.coordinates[0], end_node.coordinates[0], None], 
                         [start_node.coordinates[1], end_node.coordinates[1], None])
                    )

            animation_frames = []
            for i, (t, time_label) in enumerate(zip(frames, time_labels)):
                values = data.loc[t, :]
                hover_text = [
                    f"Node: {name}<br>Time: {time_label}<br>{parameter.capitalize()} ({unit}): {values[name]}"
                    for name in node_names if name in values.index
                ]

                animation_frames.append(go.Frame(
                    name=str(i),
                    data=[
                        go.Scatter(
                            x=sum([edge[0] for edge in adjacency_list], []),
                            y=sum([edge[1] for edge in adjacency_list], []),
                            mode="lines",
                            line=dict(color="black", width=1),
                            hoverinfo="none",
                            showlegend=False
                        ),
                        go.Scatter(
                            x=node_x, y=node_y, mode="markers",
                            marker=dict(size=6, color=values.tolist(), colorscale="viridis", showscale=True),
                            text=hover_text, hoverinfo="text",
                            showlegend=False
                        )
                    ]
                ))

            fig.add_trace(go.Scatter(
                x=sum([edge[0] for edge in adjacency_list], []),
                y=sum([edge[1] for edge in adjacency_list], []),
                mode="lines",
                line=dict(color="black", width=1),
                hoverinfo="none",
                showlegend=False
            ))

            fig.add_trace(go.Scatter(
                x=node_x, y=node_y, mode="markers",
                marker=dict(size=6, color=data.loc[frames[0], :].tolist(), colorscale="viridis", showscale=True),
                text=[f"Node: {name}<br>Time: {time_labels[0]}<br>{parameter.capitalize()} ({unit}): {data.loc[frames[0], name]}"
                      for name in node_names],
                hoverinfo="text",
                showlegend=False
            ))

        # ✅ LINK LOGIC
        else:
            link_x, link_y, link_names = [], [], []

            for link_name in wn.link_name_list:
                link = wn.get_link(link_name)
                start_node = wn.get_node(link.start_node)
                end_node = wn.get_node(link.end_node)

                if hasattr(start_node, "coordinates") and hasattr(end_node, "coordinates"):
                    link_x.append([start_node.coordinates[0], end_node.coordinates[0], None])
                    link_y.append([start_node.coordinates[1], end_node.coordinates[1], None])
                    link_names.append(link_name)

            norm = mcolors.Normalize(vmin=data.min().min(), vmax=data.max().max())
            cmap = cm.get_cmap("viridis")

            animation_frames = []
            for i, (t, time_label) in enumerate(zip(frames, time_labels)):
                values = data.loc[t, :]
                link_colors = [mcolors.to_hex(cmap(norm(values[name]))) for name in link_names if name in values.index]
                hover_text = [
                    f"Link: {name}<br>Time: {t}s<br>{parameter.capitalize()} ({unit}): {values[name]}" 
                    for name in link_names if name in values.index
                ]

                animation_frames.append(go.Frame(
                    name=str(i),
                    data=[
                        go.Scatter(
                            x=sum(link_x, []), y=sum(link_y, []), mode="lines",
                            line=dict(color="blue", width=2),
                            marker=dict(size=5, color=link_colors, colorscale="viridis", showscale=True),
                            text=hover_text, hoverinfo="text",
                            showlegend=False
                        )
                    ]
                ))

            link_colors_init = [mcolors.to_hex(cmap(norm(values[name]))) for name in link_names]

            fig.add_trace(go.Scatter(
                x=sum(link_x, []), y=sum(link_y, []), mode="lines",
                line=dict(color="blue", width=2),
                marker=dict(size=5, color=link_colors_init, colorscale="viridis", showscale=True),
                text=[f"Link: {name}<br>Time: {time_labels[0]}<br>{parameter.capitalize()} ({unit}): {values[name]}" 
                      for name in link_names],
                hoverinfo="text",
                showlegend=False
            ))

        # ✅ Restore Plotly Play/Pause Buttons (Your Required Logic)
        fig.update_layout(
            updatemenus=[{
                "buttons": [
                    {"args": [None, {"frame": {"duration": 800, "redraw": True}, "mode": "immediate"}],
                     "label": "Play", "method": "animate"},
                    {"args": [[None], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate"}],
                     "label": "Pause", "method": "animate"}
                ],
                "direction": "left",
                "pad": {"r": 10, "t": 87},
                "showactive": True,
                "type": "buttons",
                "x": 0.1,
                "xanchor": "right",
                "y": -0.15,
                "yanchor": "top"
            }]
        )

        # ✅ Apply animation frames
        fig.update(frames=animation_frames)

        fig.update_layout(
            title=f"{parameter.capitalize()} ({unit}) Data from 0 to {entered_time}",
            xaxis_title="X",
            yaxis_title="Y",
            plot_bgcolor="rgba(240,240,240,0.9)"
        )

        # ✅ Convert Plotly figure to HTML
        fig_html = fig.to_html(full_html=False)

        return f"""
            <div>{fig_html}</div>
            <br>
            <div style="overflow-x:auto; margin-top:10px;">
                <h3>{parameter.capitalize()} ({unit}) Data from 0 to {entered_time}</h3>
                {table_html}
            </div>
        """

    except Exception as e:
        print("[ERROR] Animated visualization failed:", str(e))
        return f'<p style="color:red;">[ERROR] {str(e)}</p>'


@app.route("/time_series", methods=["POST"])
def generate_time_series():
    """Generates Time Series Graph based on user selection"""
    try:
        data = request.json
        node_id = data["node_id"]

        wn = wntr.network.WaterNetworkModel(global_inp_file)
        wn.options.hydraulic.demand_model = 'PDD'
        sim = wntr.sim.WNTRSimulator(wn)
        results = sim.run_sim()

        plt.figure(figsize=(10, 5))

        if node_id.lower() == "all":
            for node in results.node["demand"].columns:
                plt.plot(results.time, results.node["demand"][node], alpha=0.5)
            plt.title("Time Series - Demand (All Nodes)")
        else:
            plt.plot(results.time, results.node["demand"][node_id], label=node_id, color="blue")
            plt.title(f"Time Series - Demand ({node_id})")
        
        plt.xlabel("Time")
        plt.ylabel("Demand")
        plt.xticks(rotation=45)
        plt.legend()
        plt.grid()

        graph_path = os.path.join(STATIC_FOLDER, "timeseries.png")
        plt.savefig(graph_path)
        plt.close()

        return "Time Series Graph Generated", 200

    except Exception as e:
        print("[ERROR] Failed to generate time series graph:", str(e))
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
