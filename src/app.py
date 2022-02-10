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
import base64

import ra_processing
import trending
import export
#import remote_admin as data


web = Flask(__name__)
SESSION_TYPE = 'filesystem'
SESSION_PERMANENT = False
web.secret_key = str(uuid.uuid4())
web.config.from_object(__name__)
Session(web)


def update_settings(settings:dict={}):
    new_settings = {}
    update = False
    if exists('ra_config/config.json'):
        f = open('ra_config/config.json')
        old_settings = json.load(f)
        f.close()
        new_settings = old_settings
        if settings:
            for setting in settings:
                if old_settings.get(setting) != settings[setting]:
                    new_settings[setting] = settings[setting]
                    update = True
    else:
        if settings:
            new_settings = settings
            update = True
        else:
            new_settings = {"url":None, "username": None, "password": None, "nodes":[]}
            update = True
    if new_settings.get('nodes'):
        if type(new_settings['nodes']) == str:
            new_settings['nodes'] = json.loads(new_settings['nodes'])
    if update:
        f = open('ra_config/config.json', 'w')
        json.dump(new_settings, f)
        f.close()
        flash('Settings Updated')
    web.my_config = new_settings

update_settings()


@web.template_filter()
def numberFormat(value):
    return "{:,.2f}".format(int(value))

def byte_metrics(metrics:list) -> list:
    metrics = [metric for metric in metrics if 'Bytes' in metric]
    metrics.reverse()
    return metrics


def get_data(redirect:redirect) -> dict:
    RA_url = web.my_config['url']
    RAauth = HTTPBasicAuth(web.my_config['username'], web.my_config['password'])

    interfaces = []
    metrics = []

    if not session.get('new_pair'):
        session['new_pair'] = 0
    session['pair'] = {"nodes":{}}
    pair = [label for label in session['pair']['nodes']]
    if not pair:
        pair = web.my_config["nodes"][session['new_pair']]

    for node in pair:
        interface_list = ra_processing.get_interfaces(RA_url, RAauth, node)
        session['pair']['nodes'][node] = {'label':interface_list['label'], 'name': interface_list['name']}
        session['pair']['nodes'][node]['ip'] = session['pair']['nodes'][node]['label'].split(' ')[0]
        session['pair']['nodes'][node]['label'] = session['pair']['nodes'][node]['label'].split(' ')[1][1:-1]
        #node_list = [interface_list['label']]
        interfaces_a, metrics_a = ra_processing.filter_interfaces(interface_list)
        [interfaces.append(interface) for interface in interfaces_a if interface not in interfaces]
        [metrics.append(metric) for metric in metrics_a if metric not in metrics]

    session['pair']['name'] = ":".join([session['pair']['nodes'][node]['label'] for node in session['pair']['nodes']])
    session['interfaces'] = interfaces
    session['metrics'] = metrics
    parsed_metrics = ra_processing.main(RA_url, RAauth, interfaces, metrics)
    session['parsed_metrics'] = parsed_metrics
    return redirect


@web.route('/clear')
@web.route('/clear/<new_pair>')
def clear_cache(new_pair:int=0):
    session.clear()
    session['new_pair'] = int(new_pair)
    return redirect(url_for('home_page'))

@web.route('/select')
def vip_list():
    if 'parsed_metrics' not in session:
        get_data(url_for('vip_list'))
    vips = [vip.replace('/Common/', '') for vip in session['parsed_metrics'] if '/Common/' in vip]
    #vips = ['Changepoint-VIP']
    pairs = {}
    for i in range(0, len(web.my_config['nodes'])):
        pairs[i] = web.my_config['nodes'][i]
    return render_template('vip_list.html', vips=vips, pairs=pairs)

@web.route('/blank')
def blank_page():
    return "Hello"

@web.route('/')
def home_page():
    if web.my_config['url'] is None:
        return redirect(url_for('settings_page'))
    if 'parsed_metrics' not in session:
        get_data(url_for('home_page'))
    vips = [vip_name.replace('/Common/', '') for vip_name in session['parsed_metrics'] if '/Common/' in vip_name]

    device_summary = trending.summary_stats(session['parsed_metrics'], 'node[device]', session['metrics'])

    return render_template('home.html', vips=vips, summary=device_summary)

@web.route('/vip')
@web.route('/vip/')
@web.route('/vip/<vip>')
def vip_page(vip:str=None):
    if web.my_config['url'] is None:
        return redirect(url_for('settings_page'))
    if 'parsed_metrics' not in session:
        get_data(url_for('vip_page', vip=vip))
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
        return redirect(url_for('vip_page', vip=vip))
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
        pdf.interface_summary(summary, 10, 30)
        pdf.add_image('temp/fig1.png', 10, 70)
        pdf.add_image('temp/fig2.png', 10, 170)

        response = make_response(pdf.output())
        response.headers.set('Content-Disposition', 'attachment', filename=vip + '.pdf')
        response.headers.set('Content-Type', 'application/pdf')
        return response
    else:
        return render_template('graph.html', vips=vips)


@web.route('/topn')
@web.route('/topn/')
@web.route('/topn/<metric>')
def top_n_page(metric:str=None):
    if 'parsed_metrics' not in session:
        return redirect(url_for('vip_page'))
    vips = [vip_name.replace('/Common/', '') for vip_name in session['parsed_metrics'] if '/Common/' in vip_name]
    if metric in session['parsed_metrics']['node[top_n]']:
        top_n = {metric: session['parsed_metrics']['node[top_n]'][metric]}
    else:
        top_n = session['parsed_metrics']['node[top_n]']
    return render_template('top_n.html', vips=vips, selected_metric=metric, top_n=top_n)


@web.route('/settings', methods=['GET', 'POST'])
def settings_page():
    if request.method == 'POST':
        update_settings(request.form.to_dict())
    with open('ra_config/logo.png', 'rb') as f:
        logoimage = base64.b64encode(f.read()).decode('utf-8')
    with open('ra_config/logo_customer.png', 'rb') as f:
        logocustomer= base64.b64encode(f.read()).decode('utf-8')
    config = dict(web.my_config)
    config['nodes'] = json.dumps(config['nodes'])
    if not session.get('pair_list'):
        pairs = [list(i) for i in web.my_config['nodes']]
        for i in range(0, len(pairs)):
            for node in range(0, len(pairs[i])):
                pairs[i][node] = ra_processing.get_interfaces(web.my_config['url'],HTTPBasicAuth(web.my_config['username'], web.my_config['password']),pairs[i][node])['label'].split(' ')[1][1:-1]
        session['pair_list'] = pairs
    return render_template('settings.html', config=config, logoimage=logoimage, logocustomer=logocustomer)
