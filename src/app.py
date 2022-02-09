# app.py

from flask import Flask, render_template, request, session, redirect, url_for, make_response, flash
from flask_session import Session
from requests.auth import HTTPBasicAuth
from os.path import exists

import json
import plotly
import plotly.express as px
import plotly.graph_objects as go
import uuid

import ra_processing
import trending
import export
#import remote_admin as data

global config

def update_settings(settings:dict={"url":None, "username": None, "password": None}):
    f = open('ra_config/config.json', 'w')
    json.dump(settings, f)
    f.close()
    config = settings

if exists('ra_config/config.json'):
    f = open('ra_config/config.json')
    config = json.load(f)
    f.close()
else:
    config = update_settings()

f = open('ra_config/node_pairs.json')
nodes = json.load(f)
nodes = nodes['nodes']
f.close()

web = Flask(__name__)
SESSION_TYPE = 'filesystem'
SESSION_PERMANENT = False
web.secret_key = str(uuid.uuid4())
web.config.from_object(__name__)
Session(web)

def byte_metrics(metrics:list) -> list:
    metrics = [metric for metric in metrics if 'Bytes' in metric]
    metrics.reverse()
    return metrics


def get_data(redirect:redirect) -> dict:
    RA_url = config['url']
    RAauth = HTTPBasicAuth(config['username'], config['password'])

    interfaces = []
    metrics = []

    for node in nodes[0]:
        interface_list = ra_processing.get_interfaces(RA_url, RAauth, node)
        #node_list = [interface_list['label']]
        interfaces_a, metrics_a = ra_processing.filter_interfaces(interface_list)
        [interfaces.append(interface) for interface in interfaces_a if interface not in interfaces]
        [metrics.append(metric) for metric in metrics_a if metric not in metrics]

    session['interfaces'] = interfaces
    session['metrics'] = metrics
    parsed_metrics = ra_processing.main(RA_url, RAauth, interfaces, metrics)
    session['parsed_metrics'] = parsed_metrics
    return redirect


@web.route('/clear')
def clear_cache():
    session.clear()
    return redirect(url_for('home_page'))

@web.route('/select')
def vip_list():
    if 'parsed_metrics' not in session:
        get_data(url_for('vip_list'))
    vips = [vip.replace('/Common/', '') for vip in session['parsed_metrics'] if '/Common/' in vip]
    #vips = ['Changepoint-VIP']
    return render_template('vip_list.html', vips=vips)

@web.route('/blank')
def blank_page():
    return "Hello"

@web.route('/')
@web.route('/vip')
@web.route('/vip/')
@web.route('/vip/<vip>')
def home_page(vip:str=None):
    if config['url'] is None:
        return redirect(url_for('settings_page'))
    if 'parsed_metrics' not in session:
        get_data(url_for('home_page', vip=vip))
    vips = [vip_name.replace('/Common/', '') for vip_name in session['parsed_metrics'] if '/Common/' in vip_name]
    if not vip:
        vip = request.args.get('vip')
    if not vip:
        vip = 'Changepoint-VIP'
    if vip in vips:
        interface = '/Common/' + vip
        weekends = trending.find_weekends(session['parsed_metrics'], interface)
        trend_time = trending.time_trend(session['parsed_metrics'], interface, byte_metrics(session['metrics']))
        trend_line = trending.time_lines(session['parsed_metrics'], interface, byte_metrics(session['metrics']))

        summary = trending.summary_stats(session['parsed_metrics'], interface, session['metrics'])

        fig1 = get_trend_graph(trend_time)
        fig2 = get_trend_line(trend_line[0], trend_line[1], weekends)

        fig1_json = json.dumps(fig1, cls=plotly.utils.PlotlyJSONEncoder)
        fig2_json = json.dumps(fig2, cls=plotly.utils.PlotlyJSONEncoder)
        return render_template('graph.html', fig1_json=fig1_json, fig2_json=fig2_json, vips=vips, selected_vip=vip, summary=summary)
    else:
        return render_template('graph.html', vips=vips)


def get_trend_graph(trend:dict) -> px.scatter:
    fig = px.scatter(x=trend['x'], y=trend['y'], size=trend['z'], color=trend['c'], labels={'x': 'Day of Week', 'y': 'Time', 'size': 'Bytes', 'color': 'Metric'})
    fig.add_shape(y0="8:00", y1="8:00", x0=-.5, x1=7.5, type="line", line_color="black", line_width=1)
    fig.add_shape(y0="17:00", y1="17:00", x0=-.5, x1=7.5, type="line", line_color="black", line_width=1)
    fig.add_vrect(x0=4.5, x1=6.5, fillcolor="LightSalmon", opacity=0.5, layer="below", line_width=0)
    return fig

def get_trend_line(stats:dict, stats2:dict, weekends:dict) -> go.Figure:
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=stats['x'], y=stats['y'], mode="lines", name="BytesOut"))
    fig2.add_trace(go.Scatter(x=stats2['x'], y=stats2['y'], mode="lines", name="BytesIn"))
    #fig2.add_shape(y0="8:00", y1="8:00", x0=-.5, x1=6.5, type="line", line_color="black", line_width=1)
    #fig2.add_shape(y0="17:00", y1="17:00", x0=-.5, x1=6.5, type="line", line_color="black", line_width=1)
    for weekend in weekends:
        fig2.add_vrect(x0=weekend[0], x1=weekend[1], fillcolor="LightSalmon", opacity=0.5, layer="below", line_width=0)
    #fig.add_vrect(x0=4.5, x1=6.5, fillcolor="LightSalmon", opacity=0.5, layer="below", line_width=0)
    return fig2

@web.route('/pdf/<vip>')
def pdf(vip:str=None):
    if 'parsed_metrics' not in session:
        return redirect(url_for('home_page', vip=vip))
    vips = [vip_name.replace('/Common/', '') for vip_name in session['parsed_metrics'] if '/Common/' in vip_name]
    if not vip:
        vip = request.args.get('vip')
    if not vip:
        vip = 'Changepoint-VIP'
    if vip in vips:
        interface = '/Common/' + vip
        weekends = trending.find_weekends(session['parsed_metrics'], interface)
        trend_time = trending.time_trend(session['parsed_metrics'], interface, byte_metrics(session['metrics']))
        trend_line = trending.time_lines(session['parsed_metrics'], interface, byte_metrics(session['metrics']))

        summary = trending.summary_stats(session['parsed_metrics'], interface, session['metrics'])

        fig1 = get_trend_graph(trend_time)
        fig2 = get_trend_line(trend_line[0], trend_line[1], weekends)

        plotly.io.write_image(fig1, file="temp/fig1.png", format='png', width=900, height=500)
        plotly.io.write_image(fig2, file="temp/fig2.png", format='png', width=900, height=500)

        pdf = export.generate_pdf(vip)
        pdf.add_summary(summary, 10, 30)
        pdf.add_image('temp/fig1.png', 10, 70)
        pdf.add_image('temp/fig2.png', 10, 170)

        response = make_response(pdf.output())
        response.headers.set('Content-Disposition', 'attachment', filename=vip + '.pdf')
        response.headers.set('Content-Type', 'application/pdf')
        return response
    else:
        return render_template('graph.html', vips=vips)

@web.route('/settings', methods=['GET', 'POST'])
def settings_page():
    if request.method == 'POST':
        update_settings(request.form.to_dict())
    if 'parsed_metrics' not in session and config['url'] is not None:
        get_data(url_for('settings_page'))
        vips = [vip.replace('/Common/', '') for vip in session['parsed_metrics'] if '/Common/' in vip]
    else:
        vips = []
    return render_template('settings.html', vips=vips, config=config)
