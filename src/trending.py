# trending.py
# cspell:ignore tozeroy

# Generate trending stats on processed metrics

from datetime import datetime
from models import Day
from ra_processing import average_metrics

import plotly.express as px
import plotly.graph_objects as go

def byte_metrics(metrics:list) -> list:
    """Filter all metrics to only include those related to bytes

    Args:
        metrics (list): List of all metrics found on nodes

    Returns:
        list: List of filtered metrics
    """
    metrics = [metric for metric in metrics if 'Bytes' in metric]
    return list(set(metrics))

def time_trend(parsed_metrics:dict, interface:str, label:list) -> dict:
    """Generate dataset for Plotly scatter graph of most active days/times

    Args:
        parsed_metrics (dict): Data for all found interfaces
        interface (str): Name of the interface to be analyzed
        label (list): List of metrics to include in the graph

    Returns:
        dict: Data for Plotly scatter graph
    """
    trend = {'x': [], 'y': [], 'z': [], 'c': [], 'hour':{}}
    for j in parsed_metrics[interface]['day_of_week']:
        if j != 'total':
            for k in parsed_metrics[interface]['day_of_week'][j]:
                for metric in label:
                    if 'out' in metric.lower():
                        if metric in parsed_metrics[interface]['day_of_week'][j][k]:
                            trend['x'].append(Day(j).name)
                            if k == 'total':
                                trend['y'].append(f'average')
                            else:
                                trend['y'].append(f'{k}:00')
                            if parsed_metrics[interface]['day_of_week'][j][k][metric] != None:
                                trend['z'].append(parsed_metrics[interface]['day_of_week'][j][k][metric] or 0)
                            else:
                                trend['z'].append(0)
                            trend['c'].append('Bytes Out')
                    elif 'in' in metric.lower():
                        if metric in parsed_metrics[interface]['day_of_week'][j][k]:
                            trend['x'].append(Day(j).name)
                            if k == 'total':
                                trend['y'].append(f'average')
                            else:
                                trend['y'].append(f'{k}:00')
                            if parsed_metrics[interface]['day_of_week'][j][k][metric] != None:
                                trend['z'].append(parsed_metrics[interface]['day_of_week'][j][k][metric] or 0)
                            else:
                                trend['z'].append(0)
                            trend['c'].append('Bytes In')
    for k in parsed_metrics[interface]['hour_of_day']:
        trend['hour'][k] = {'Bytes Out': [], 'Bytes In': []}
        for metric in label:
            if 'out' in metric.lower():
                trend['hour'][k]['Bytes Out'].append(parsed_metrics[interface]['hour_of_day'][k].get(metric) or 0)
            elif 'in' in metric.lower():
                trend['hour'][k]['Bytes In'].append(parsed_metrics[interface]['hour_of_day'][k].get(metric) or 0)
    for k in parsed_metrics[interface]['hour_of_day']:
        trend['hour'][k] = average_metrics(trend['hour'][k])
    for k in trend['hour']:
        for metric in trend['hour'][k]:
            if trend['hour'][k].get(metric):
                trend['x'].append('Average')
                trend['y'].append(f'{k}:00')
                trend['z'].append(trend['hour'][k][metric])
                trend['c'].append(metric)
    return trend


def find_weekends(parsed_metrics:dict, interface:str) -> list:
    """Determine weekends for Plotly line graph shading

    Args:
        parsed_metrics (dict): Data for all found interfaces
        interface (str): Name of the interface to be analyzed

    Returns:
        list: List of start/end timestamps for weekends
    """
    weekends = []
    weekend_start = []
    weekend_end = []
    is_weekend = []
    previous_day = None
    current_day = None
    for i in parsed_metrics:
        if i == interface:
            #print(parsed_metrics[i]['day_of_week'])
            for j in parsed_metrics[i]['ts']:
                date = datetime.fromtimestamp(j/1000)
                day = date.weekday()
                if day == 5 or day == 6:
                    current_day = True
                    if current_day and not previous_day:
                        weekend_start.append(date)
                else:
                    current_day = False
                    if not current_day and previous_day:
                        weekend_end.append(date)
                is_weekend.append({j:current_day})
                previous_day = current_day
        if current_day:
            weekend_end.append(date)

    for ts in range(0, len(weekend_start)):
        weekends.append([weekend_start[ts], weekend_end[ts]])

    return weekends


def time_lines(parsed_metrics:dict, interface:str, label:list) -> dict:
    """Generate data for Plotly line graph

    Args:
        parsed_metrics (dict): Data for all found interfaces
        interface (str): Name of the interface to be analyzed
        label (list): Metrics to include in the graph

    Returns:
        dict: Set of datasets for Plotly line graph
    """
    stats_out = {'x': [], 'y': []}
    stats_in = {'x': [], 'y': []}
    for i in parsed_metrics:
        if i == interface:
            for j in parsed_metrics[i]['ts']:
                date = datetime.fromtimestamp(j/1000)
                for metric in label:
                    if 'out' in metric.lower():
                        if parsed_metrics[i]['ts'][j].get(metric) not in [None, [None]]:
                            stats_out['y'].append(parsed_metrics[i]['ts'][j].get(metric) * -1)
                        else:
                            stats_out['y'].append(0)
                        stats_out['x'].append(date)
                    elif 'in' in metric.lower():
                        stats_in['x'].append(date)
                        if parsed_metrics[i]['ts'][j].get(metric) not in [None, [None]]:
                            stats_in['y'].append(parsed_metrics[i]['ts'][j].get(metric))
                        else:
                            stats_in['y'].append(0)
        if len(stats_out['x']) >= 100:
            break
    return stats_out, stats_in

theme = {'out': '#204a87', 'in': '#4e9a06', 'weekend': 'rgba(126,129,157,1)', 'outfill': '#3465a4', 'infill': '#73d216'}

def get_trend_graph(trend:dict, margin:int=80) -> px.scatter:
    """Generate Plotly time trend graph

    Args:
        trend (dict): Graph dataset from time_trend()

    Returns:
        px.scatter: Scatter plot of time trends
    """
    fig = px.scatter(x=trend['x'], y=trend['y'], size=trend['z'], color=trend['c'], labels={'x': 'Day of Week', 'y': 'Time', 'size': 'Bytes', 'color': 'Metric'}, color_discrete_map={"Bytes Out": theme['out'], "Bytes In": theme['in']})
    fig.add_shape(y0="8:00", y1="8:00", x0=-.5, x1=7.5, type="line", line_color="black", line_width=1)
    if '17:00' in trend['y']:
        fig.add_shape(y0="17:00", y1="17:00", x0=-.5, x1=7.5, type="line", line_color="black", line_width=1)
    else:
        fig.add_shape(y0="18:00", y1="18:00", x0=-.5, x1=7.5, type="line", line_color="black", line_width=1)
    fig.add_vrect(x0=4.5, x1=6.5, fillcolor=theme['weekend'], opacity=0.25, layer="below", line_width=0)
    fig.layout.margin.l = margin
    fig.layout.margin.r = margin
    fig.layout.margin.t = margin
    fig.layout.margin.b = margin
    return fig

def get_trend_line(stats_out:dict, stats_in:dict, weekends:dict, margin:int=80) -> go.Figure:
    """Generate Plotly line graph of raw traffic data

    Args:
        stats_out (dict): Output data from time_lines()
        stats_in (dict): Output data from time_lines()
        weekends (dict): Output from find_weekends()

    Returns:
        go.Figure: Line graph of traffic
    """
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=stats_out['x'], y=stats_out['y'], mode="lines", name="BytesOut", line={'color':theme['out']}, fill='tozeroy', fillcolor=theme['outfill']))
    fig2.add_trace(go.Scatter(x=stats_in['x'], y=stats_in['y'], mode="lines", name="BytesIn", line={'color':theme['in']}, fill='tozeroy', fillcolor=theme['infill']))
    for weekend in weekends:
        fig2.add_vrect(x0=weekend[0], x1=weekend[1], fillcolor=theme['weekend'], opacity=0.25, layer="below", line_width=0)
    fig2.layout.margin.l = margin
    fig2.layout.margin.r = margin
    fig2.layout.margin.t = margin
    fig2.layout.margin.b = margin
    return fig2
