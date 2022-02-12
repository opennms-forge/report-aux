# app.py

from flask import Flask, render_template, request, session, redirect, url_for, make_response, flash
from flask_session import Session
from requests.auth import HTTPBasicAuth
from os.path import exists

import json
import plotly
import uuid
import base64
import os

import ra_processing
import trending
import export
#import remote_admin as data


web = Flask(__name__)
SESSION_TYPE = 'filesystem'
SESSION_PERMANENT = False
web.secret_key = "not_so_secret" #str(uuid.uuid4())
web.config.from_object(__name__)
Session(web)

def clear_temp(session:bool=False):
    if session:
        session_files = os.scandir('flask_session')
        for file in session_files:
            os.remove(file.path)
    temp_files = os.scandir('temp')
    for file in temp_files:
        if '.readme' not in file.name:
            os.remove(file.path)

clear_temp(session=False)

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

@web.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', error=e), 403

@web.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', error=e), 404

@web.errorhandler(410)
def page_not_found(e):
    return render_template('error.html', error=e), 410

@web.errorhandler(500)
def page_not_found(e):
    return render_template('error.html', error=e), 500


@web.template_filter()
def numberFormat(value:float, round:int=2) -> str:
    num_format = "{:,." + str(round) + "f}"
    return num_format.format(float(value))

@web.context_processor
def global_vars():
    vars = {
        'og_title':'OpenNMS Auxiliary Reports',
        'og_description':'Custom trending and reporting for OpenNMS',
    }
    return vars


def get_data(redirect:redirect) -> dict:
    RA_url = web.my_config['url']
    RAauth = HTTPBasicAuth(web.my_config['username'], web.my_config['password'])

    interfaces = []
    metrics = []

    if not session.get('new_pair'):
        session['new_pair'] = 0
    if not session.get('pair'):
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
    session['vips'] = [vip.replace('/Common/', '') for vip in parsed_metrics if '/Common/' in vip]
    session['parsed_metrics'] = parsed_metrics

    return redirect


@web.route('/clear')
@web.route('/clear/<new_pair>')
def clear_cache(new_pair:int=0):
    cookies = ['parsed_metrics', 'pair', 'interfaces', 'metrics', 'vips']
    for cookie in cookies:
        if cookie in session:
            session.pop(cookie)
    session['new_pair'] = int(new_pair)
    clear_temp()
    return redirect(url_for('home_page'))

@web.route('/select')
def vip_list():
    pairs = {}
    for i in range(0, len(web.my_config['nodes'])):
        pairs[i] = web.my_config['nodes'][i]
    return render_template('vip_list.html', pairs=pairs)

@web.route('/blank')
def blank_page():
    return "Hello"

@web.route('/')
def home_page():
    if web.my_config['url'] is None:
        return redirect(url_for('settings_page'))
    if 'parsed_metrics' not in session:
        get_data(url_for('vip_page'))
    if session['parsed_metrics']['node[device]'].get('stats'):
        weekends = trending.find_weekends(session['parsed_metrics'], 'node[device]')
        metric_list = trending.byte_metrics(session['metrics'])
        trend_time = trending.time_trend(session['parsed_metrics'], 'node[device]', metric_list)
        trend_line = trending.time_lines(session['parsed_metrics'], 'node[device]', metric_list)

        fig1 = trending.get_trend_graph(trend_time)
        fig2 = trending.get_trend_line(trend_line[0], trend_line[1], weekends)

        fig1_json = json.dumps(fig1, cls=plotly.utils.PlotlyJSONEncoder)
        fig2_json = json.dumps(fig2, cls=plotly.utils.PlotlyJSONEncoder)
    else:
        fig1_json = json.dumps({})
        fig2_json = json.dumps({})
    return render_template('home.html', fig1_json=fig1_json, fig2_json=fig2_json, summary=session['parsed_metrics']['node[device]']['stats'])

@web.route('/vip')
def vip_page(vip:str=None):
    if web.my_config['url'] is None:
        return redirect(url_for('settings_page'))
    if 'parsed_metrics' not in session:
        get_data(url_for('vip_page', vip=vip))
    if not vip:
        vip = request.args.get('vip')
    if not vip:
        vip = session['vips'][0]
    if vip in session['vips']:
        interface = '/Common/' + vip
        weekends = trending.find_weekends(session['parsed_metrics'], interface)
        metric_list = trending.byte_metrics(session['metrics'])
        trend_time = trending.time_trend(session['parsed_metrics'], interface, metric_list)
        trend_line = trending.time_lines(session['parsed_metrics'], interface, metric_list)

        fig1 = trending.get_trend_graph(trend_time)
        fig2 = trending.get_trend_line(trend_line[0], trend_line[1], weekends)

        fig1_json = json.dumps(fig1, cls=plotly.utils.PlotlyJSONEncoder)
        fig2_json = json.dumps(fig2, cls=plotly.utils.PlotlyJSONEncoder)
        return render_template('graph.html', fig1_json=fig1_json, fig2_json=fig2_json, selected_vip=vip, summary=session['parsed_metrics'][interface]['stats'])
    else:
        return render_template('graph.html')


@web.route('/node_pdf')
def node_pdf():
    if 'parsed_metrics' not in session:
        return redirect(url_for('home_page'))
    pdf = export.render_node_pdf(pair_name=session['pair']['name'], vips=session['vips'], parsed_metrics=session['parsed_metrics'], metrics=trending.byte_metrics(session['metrics']))
    response = make_response(pdf.output())
    response.headers.set('Content-Disposition', 'attachment', filename=session['pair']['name'].replace(':','_') + '.pdf')
    response.headers.set('Content-Type', 'application/pdf')
    return response

@web.route('/vip_pdf')
def vip_pdf(vip:str=None):
    if 'parsed_metrics' not in session:
        return redirect(url_for('vip_page', vip=vip))
    if not vip:
        vip = request.args.get('vip')
    if not vip:
        vip = session['vips'][0]
    if vip in session['vips']:
        pdf = export.render_vip_pdf(pair_name=session['pair']['name'], vip=vip, parsed_metrics=session['parsed_metrics'], metrics=trending.byte_metrics(session['metrics']))
        response = make_response(pdf.output())
        response.headers.set('Content-Disposition', 'attachment', filename=vip + '.pdf')
        response.headers.set('Content-Type', 'application/pdf')
        return response
    else:
        return render_template('graph.html')


@web.route('/topn')
@web.route('/topn/')
@web.route('/topn/<metric>')
def top_n_page(metric:str=None):
    if 'parsed_metrics' not in session:
        return redirect(url_for('vip_page'))
    if metric in session['parsed_metrics']['node[top_n]']:
        top_n = {metric: session['parsed_metrics']['node[top_n]'][metric]}
    else:
        top_n = session['parsed_metrics']['node[top_n]']
    return render_template('top_n.html', selected_metric=metric, top_n=top_n)


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
        session['pair_list'] = list(pairs)
    pair_list = []
    for pair in session['pair_list']:
        pair_list.append(":".join(pair))
    return render_template('settings.html', config=config, logoimage=logoimage, logocustomer=logocustomer, pair_list=pair_list)

@web.route('/all_nodes')
def all_report_page():
    files = []
    zip = [None]
    pdf_files = os.scandir('static/pdf')
    for file in pdf_files:
        if '.pdf' in file.name:
            files.append(file)
    zip_files = os.scandir('static')
    for file in zip_files:
        if '.zip' in file.name:
            zip = [file]
    return render_template('all_nodes.html', files=files, zip=zip)
