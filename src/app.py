# app.py

# Flask web front end

from datetime import datetime
from flask import Flask, render_template, request, session, redirect, url_for, make_response, flash
from flask_session import Session
from requests.auth import HTTPBasicAuth
from os.path import exists

import json
import plotly
import base64
import os
import time

import ra_processing
import trending
import export


web = Flask(__name__)
SESSION_TYPE = 'filesystem'
SESSION_PERMANENT = False
web.secret_key = "not_so_secret"
web.config.from_object(__name__)
Session(web)

def clear_temp(session:bool=False):
    """Clear temporary files from disk

    Args:
        session (bool, optional): Clear user session cache.
        Defaults to False.
    """
    if session:
        session_files = os.scandir('flask_session')
        for file in session_files:
            os.remove(file.path)
    temp_files = os.scandir('temp')
    for file in temp_files:
        if '.readme' not in file.name:
            os.remove(file.path)

clear_temp(session=False)

def get_pair_list() -> None:
    """Get names of pairs from OpenNMS instance"""
    pairs = [list(i) for i in web.my_config['nodes']]
    for i in range(0, len(pairs)):
        for node in range(0, len(pairs[i])):
            pairs[i][node] = ra_processing.get_interfaces(web.my_config['url'],HTTPBasicAuth(web.my_config['username'], web.my_config['password']),pairs[i][node])['label'].split(' ')[1][1:-1]
    web.pair_list = list(pairs)

def update_settings(settings:dict={}):
    """Get/Write settings to disk

    Args:
        settings (dict, optional): New settings to write to file.
        If not provided, will read existing settings from disk.
        Defaults to {}.
    """
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
            new_settings['nodes'] = sorted(new_settings['nodes'])
    if update:
        f = open('ra_config/config.json', 'w')
        json.dump(new_settings, f)
        f.close()
        flash('Settings Updated')
        get_pair_list()
    web.my_config = new_settings

update_settings()
get_pair_list()

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
    """Formats numbers with commas and decimals

    Args:
        value (float): Number to format
        round (int, optional): Number of decimals to round. Defaults to 2.

    Returns:
        str: String representation of formatted number
    """
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
    """Get data from remote OpenNMS instance

    Args:
        redirect (redirect): URL to redirect user after retreiving data.

    Returns:
        dict: Data from remote OpenNMS instance
    """    """"""
    RA_url = web.my_config['url']
    RAauth = HTTPBasicAuth(web.my_config['username'], web.my_config['password'])

    interfaces = []
    metrics = []
    epoch = datetime.utcfromtimestamp(0)
    if not session.get('new_pair'):
        session['new_pair'] = 0
    if not session.get('pair'):
        session['pair'] = {"nodes":{}}
    pair = [label for label in session['pair']['nodes']]
    if not pair:
        pair = web.my_config["nodes"][session['new_pair']]
    if session.get('start_date'):
        start_date = int((session['start_date'] - epoch).total_seconds()) * 1000
    else:
        start_date = None
    if session.get('end_date'):
        end_date = int((session['end_date'] - epoch).total_seconds()) * 1000
    else:
        end_date = None

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
    parsed_metrics = ra_processing.main(
        base_url=RA_url,
        auth=RAauth,
        interfaces=interfaces,
        metric_labels=metrics,
        data_start=start_date,
        data_end=end_date
    )
    session['vips'] = [vip.replace('/Common/', '') for vip in parsed_metrics if '/Common/' in vip]
    session['parsed_metrics'] = parsed_metrics

    return redirect

@web.route('/clear', methods=['GET', 'POST'])
@web.route('/clear/<new_pair>', methods=['GET', 'POST'])
def clear_cache(new_pair:int=0):
    """Clear user's session cache

    Args:
        new_pair (int, optional): Specify node pair to load on next page. Defaults to 0.
    """
    cookies = ['parsed_metrics', 'pair', 'interfaces', 'metrics', 'vips' ,'start_date', 'end_date']
    for cookie in cookies:
        if cookie in session:
            session.pop(cookie)
    if request.method == 'POST':
        selection = request.form.to_dict()
        if selection.get('pairselect'):
            session['new_pair'] = int(selection['pairselect'])
        if selection.get('start_date'):
            session['start_date'] = datetime.strptime(selection['start_date'], '%Y-%m-%d')
        if selection.get('end_date'):
            session['end_date'] = datetime.strptime(f"{selection['end_date']} 23:59:59", '%Y-%m-%d %H:%M:%S')
    elif request.method == 'GET':
        session['new_pair'] = int(new_pair)
    clear_temp()
    return render_template('clear.html', title="Loading Data", message="Please wait while loading metrics")

@web.route('/loading')
def loading_page():
    if 'parsed_metrics' not in session:
        get_data(url_for('pair_page'))
    return redirect(url_for('pair_page'))

@web.route('/')
def home_page():
    if not hasattr(web, 'pair_list'):
        get_pair_list()
    pair_list = []
    for pair in web.pair_list:
        pair_list.append(":".join(pair))
    return render_template('home.html', pair_list=pair_list)

@web.route('/pair')
def pair_page():
    """Summary page for pair of nodes"""
    if web.my_config['url'] is None:
        return redirect(url_for('settings_page'))
    if 'parsed_metrics' not in session:
        return redirect(url_for('clear_cache'))
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
    return render_template('pair.html', fig1_json=fig1_json, fig2_json=fig2_json, summary=session['parsed_metrics']['node[device]']['stats'])

@web.route('/vip')
def vip_page(vip:str=None):
    """Summary page for a single VIP

    Args:
        vip (str, optional): Name of VIP to filter.
        If omitted, renders first VIP found.
        Defaults to None.
    """
    if web.my_config['url'] is None:
        return redirect(url_for('settings_page'))
    if 'parsed_metrics' not in session:
        return redirect(url_for('clear_cache'))
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
    """Generate PDF of node summary"""
    if 'parsed_metrics' not in session:
        return redirect(url_for('pair_page'))
    start_time = time.time()
    pdf = export.render_node_pdf(pair_name=session['pair']['name'], vips=session['vips'], parsed_metrics=session['parsed_metrics'], metrics=trending.byte_metrics(session['metrics']))
    response = make_response(pdf.output())
    filename = f"{session['pair']['name'].replace(':','_')}_{datetime.fromtimestamp(start_time).strftime('%Y_%m_%d_%H_%M')}.pdf"
    pdf.output(f"static/pdf/{filename}", 'F')
    response.headers.set('Content-Disposition', 'attachment', filename=filename)
    response.headers.set('Content-Type', 'application/pdf')
    return response

@web.route('/vip_pdf')
def vip_pdf(vip:str=None):
    """Generate PDF of node summary

    Args:
        vip (str, optional): Name of VIP to filter.
        If omitted, renders first VIP found.
        Defaults to None.
    """
    if 'parsed_metrics' not in session:
        return redirect(url_for('vip_page', vip=vip))
    if not vip:
        vip = request.args.get('vip')
    if not vip:
        vip = session['vips'][0]
    if vip in session['vips']:
        start_time = time.time()
        pdf = export.render_vip_pdf(pair_name=session['pair']['name'], vip=vip, parsed_metrics=session['parsed_metrics'], metrics=trending.byte_metrics(session['metrics']))
        response = make_response(pdf.output())
        filename = f"{vip}_{datetime.fromtimestamp(start_time).strftime('%Y_%m_%d_%H_%M')}.pdf"
        response.headers.set('Content-Disposition', 'attachment', filename=filename)
        response.headers.set('Content-Type', 'application/pdf')
        return response
    else:
        return render_template('graph.html')


@web.route('/topn')
@web.route('/topn/')
@web.route('/topn/<metric>')
def top_n_page(metric:str=None):
    """Renders TopN page of VIPs in pair

    Args:
        metric (str, optional): Name of metric to filter results by.
        Defaults to None.
    """
    if 'parsed_metrics' not in session:
        return redirect(url_for('vip_page'))
    if metric in session['parsed_metrics']['node[top_n]']:
        top_n = {metric: session['parsed_metrics']['node[top_n]'][metric]}
    else:
        top_n = session['parsed_metrics']['node[top_n]']
    return render_template('top_n.html', selected_metric=metric, top_n=top_n)


@web.route('/settings', methods=['GET', 'POST'])
def settings_page():
    """View and update application settings"""
    if request.method == 'POST':
        update_settings(request.form.to_dict())
    with open('ra_config/logo.png', 'rb') as f:
        logoimage = base64.b64encode(f.read()).decode('utf-8')
    with open('ra_config/logo_customer.png', 'rb') as f:
        logocustomer= base64.b64encode(f.read()).decode('utf-8')
    config = dict(web.my_config)
    config['nodes'] = json.dumps(config['nodes'])
    return render_template('settings.html', config=config, logoimage=logoimage, logocustomer=logocustomer)

@web.route('/all_nodes')
def all_report_page():
    """List all cached PDF files from report generation"""
    files = []
    zip = [None]
    pdf_files = os.listdir('static/pdf')
    for file in pdf_files:
        if '.pdf' in file:
            files.append(file)
    zip_files = os.listdir('static')
    for file in zip_files:
        if '.zip' in file:
            zip = [file]
    return render_template('all_nodes.html', files=files, zip=zip)
