# ra_processing.py

# Collect data from OpenNMS instance

from collections import Counter
from requests.auth import HTTPBasicAuth
from urllib.parse import quote
from datetime import datetime
import requests
import numpy as np
import collections
import time
import json


def get_data(url:str, auth:HTTPBasicAuth) -> dict:
    """Retreive data from OpenNMS API

    Args:
        url (str): URL to OpenNMS API
        auth (HTTPBasicAuth): Authentication credentials

    Returns:
        dict: Raw API response
    """
    headers = {'Accept': 'application/json'}
    print('Getting data from: ' + url)
    data = requests.get(url, auth=auth, headers=headers)
    return data.json()


def post_data(url:str, auth:HTTPBasicAuth, payload:dict) -> dict:
    """Post data to OpenNMS API

    Args:
        url (str): URL to OpenNMS API
        auth (HTTPBasicAuth): Authentication credentials
        payload (dict): Data to post

    Returns:
        dict: Raw API response
    """
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    print(f"Getting data from: {url}/{payload['source'][0]['resourceId']}")
    data = requests.post(url, auth=auth, headers=headers, data=json.dumps(payload))
    return data.json()


def blank_histogram() -> dict:
    """Generate default dict for interface

    Returns:
        dict: Blank interface template
    """
    blank = {'ts':{}, 'summary':{}}
    blank['day_of_week'] = {0:{'total':{}}, 1:{'total':{}}, 2:{'total':{}}, 3:{'total':{}}, 4:{'total':{}}, 5:{'total':{}}, 6:{'total':{}}}
    blank['hour_of_day'] = {}
    for hour in range(0,24):
        blank['hour_of_day'][hour] = {}
        for day in range(0,7):
            blank['day_of_week'][day][hour] = {}
    return blank

def average_metrics(metrics:dict) -> dict:
    """Calculate average data for provided metrics

    Args:
        metrics (dict): Dictionary of metrics with list of values

    Returns:
        dict: Dictionary of metrics with average value
    """
    for metric in metrics:
        if type(metrics[metric]) is list:
            metrics[metric] = [item for item in metrics[metric] if item != None]
            if metrics[metric] != None and metrics[metric] != [None] and metrics[metric] != []:
                metrics[metric] = np.mean(metrics[metric])
            elif metrics[metric] == [None]:
                metrics[metric]  = None
            elif metrics[metric] == []:
                metrics[metric] = None
    return metrics

def average_lists(parsed_metrics:dict) -> dict:
    """Calculate average data for provided metrics

    Args:
        parsed_metrics (dict): Dict of interface with lists of collected metrics

    Returns:
        dict: Dict of interface with averaged metrics
    """
    if parsed_metrics.get('ts'):
        for ts in parsed_metrics['ts']:
            parsed_metrics['ts'][ts] = average_metrics(parsed_metrics['ts'][ts])
    if parsed_metrics.get('hour_of_day'):
        for hour in range(0,24):
            parsed_metrics['hour_of_day'][hour] = average_metrics(parsed_metrics['hour_of_day'][hour])
            for day in range(0,7):
                parsed_metrics['day_of_week'][day][hour] = average_metrics(parsed_metrics['day_of_week'][day][hour])
                parsed_metrics['day_of_week'][day]['total'] = average_metrics(parsed_metrics['day_of_week'][day]['total'])
    if parsed_metrics.get('summary'):
        parsed_metrics['summary'] = average_metrics(parsed_metrics['summary'])
    return parsed_metrics


def top_n_stats(parsed_metrics:dict) -> dict:
    """Generate Top N stats for all VIPs collected

    Args:
        parsed_metrics (dict): Collected metrics for all interfaces

    Returns:
        dict: TopN data for all interfaces
    """
    top_n = {}
    trimmed_n = {}
    sorted_top_n = {}
    for interface in parsed_metrics:
        if 'node[' not in interface:
            for metric in parsed_metrics[interface]['summary']:
                if top_n.get(metric):
                    top_n[metric][interface] = parsed_metrics[interface]['summary'][metric]
                else:
                    top_n[metric] = {interface: parsed_metrics[interface]['summary'][metric]}
    for metric in top_n:
        trimmed_n[metric] = {}
        for vip in top_n[metric]:
            if round(top_n[metric][vip] or 0,2) not in [None, 0]:
                trimmed_n[metric][vip] = top_n[metric][vip]
        d = Counter(trimmed_n[metric])
        sorted_top_n[metric] = {}
        for k,v in d.most_common():
            sorted_top_n[metric][k] = v
    return sorted_top_n


def device_stats(parsed_metrics:dict) -> dict:
    """Summarize data for all VIPs on device pair

    Args:
        parsed_metrics (dict): Dict of all interfaces with collected metrics

    Returns:
        dict: Summary average for device pair
    """
    device = {}
    for interface in parsed_metrics:
        if 'node[' not in interface:
            for metric in parsed_metrics[interface]['summary']:
                if device.get(metric):
                    device[metric].append(parsed_metrics[interface]['summary'][metric])
                else:
                    device[metric] = [parsed_metrics[interface]['summary'][metric]]
    for key in parsed_metrics['node[device]']:
        device[key] = parsed_metrics['node[device]'][key]
    return device


def add_metrics(url:str, interface:str, parsed_metrics:dict, auth:HTTPBasicAuth, metrics:list, start:int, step:int=1) -> dict:
    """Add metrics to collected data for specific VIP

    Args:
        url (str): URL to OpenNMS API
        interface (str): Interface name to collect
        parsed_metrics (dict): Previously collected metrics
        auth (HTTPBasicAuth): Authentication credentials
        metrics (list): List of metrics to reqiest
        start (int): Timestamp for start of data to request
        step (int, optional): Step between timestamps to reqest. Defaults to 1.

    Returns:
        dict: Previously collected metrics with new metrics added
    """
    payload = {
        "start": start * -1,
        "step": step,
        "source": [],
        "expression": []
    }
    for metric in metrics:
        if 'in' in metric.lower():
            payload['source'].append({
                "aggregation": "AVERAGE",
                "attribute": metric,
                "label": metric,
                "resourceId": interface,
                "transient": "false"
            })
            # payload['expression'].append({
            #     "label": f"{metric}Neg",
            #     "value": f"-1.0 * {metric}",
            #     "transient": "false"
            # })
        else:
            payload['source'].append({
                "aggregation": "AVERAGE",
                "attribute": metric,
                "label": metric,
                "resourceId": interface,
                "transient": "false"
            })

    metric_data = post_data(url, auth=auth, payload=payload)

    for i in range(0, len(metric_data['timestamps'])):
        ts = metric_data['timestamps'][i]
        date = datetime.fromtimestamp(ts/1000)
        hour = date.hour
        day = date.weekday()
        for z in range(0, len(metric_data['columns'])):
            column = metric_data['columns'][z]['values'][i]
            if column == 'NaN':
                column = None

            data_point = metric_data['metadata']['resources'][z]['label']
            parsed_metrics[interface]['label'] = data_point
            metric = metric_data['labels'][z]

            if parsed_metrics[interface]['ts'].get(ts):
                parsed_metrics[interface]['ts'][ts][metric] = column
                parsed_metrics[interface]['ts'][ts]['timestamp'] = ts
                parsed_metrics[interface]['ts'][ts]['day'] = day
            else:
                parsed_metrics[interface]['ts'][ts] = {metric: column, 'timestamp': ts, 'day': day}

            for label in [data_point, 'node[device]']:
                if not parsed_metrics.get(label):
                    parsed_metrics[label] = blank_histogram()

                if parsed_metrics[label]['ts'].get(ts):
                    if parsed_metrics[label]['ts'][ts].get(metric):
                        parsed_metrics[label]['ts'][ts][metric].append(parsed_metrics[interface]['ts'][ts][metric])
                    else:
                        parsed_metrics[label]['ts'][ts][metric] = [parsed_metrics[interface]['ts'][ts][metric]]
                else:
                    parsed_metrics[label]['ts'][ts] = {metric: [parsed_metrics[interface]['ts'][ts][metric]]}

                if parsed_metrics[label]['day_of_week'][day]['total'].get(metric):
                    parsed_metrics[label]['day_of_week'][day]['total'][metric].append(parsed_metrics[interface]['ts'][ts][metric])
                else:
                    parsed_metrics[label]['day_of_week'][day]['total'][metric] = [parsed_metrics[interface]['ts'][ts][metric]]

                if parsed_metrics[label]['hour_of_day'][hour].get(metric):
                    parsed_metrics[label]['hour_of_day'][hour][metric].append(parsed_metrics[interface]['ts'][ts][metric])
                    if parsed_metrics[label]['day_of_week'][day][hour].get(metric):
                        parsed_metrics[label]['day_of_week'][day][hour][metric].append(parsed_metrics[interface]['ts'][ts][metric])
                    else:
                        parsed_metrics[label]['day_of_week'][day][hour][metric] = [parsed_metrics[interface]['ts'][ts][metric]]
                else:
                    parsed_metrics[label]['hour_of_day'][hour][metric] = [parsed_metrics[interface]['ts'][ts][metric]]
                    parsed_metrics[label]['day_of_week'][day][hour][metric] = [parsed_metrics[interface]['ts'][ts][metric]]

                if parsed_metrics[label]['summary'].get(metric):
                    parsed_metrics[label]['summary'][metric].append(parsed_metrics[interface]['ts'][ts][metric])
                else:
                    parsed_metrics[label]['summary'][metric] = [parsed_metrics[interface]['ts'][ts][metric]]

    parsed_metrics[label]['ts'] = dict(collections.OrderedDict(sorted(parsed_metrics[label]['ts'].items())))

    return parsed_metrics


def main(base_url:str, auth:HTTPBasicAuth, interfaces:list, metric_labels:list=[]) -> dict:
    start_time = time.time()
    parsed_metrics = {'node[device]': {}}
    parsed_metrics['node[data]'] = {'generated':datetime.now()}

    minute = 60000
    hour = minute * 60
    day = hour * 24
    week = day * 7
    month = day * 30
    step = 1
    loop_count = 0

    for interface in interfaces:
        loop_count += 1
        #if loop_count > 10:
        #    break
        parsed_metrics[interface] = {'ts':{}}

        metric_url = f'{base_url}measurements'
        parsed_metrics = add_metrics(metric_url, interface, parsed_metrics, auth, metric_labels, month, step)
        #for label in metric_labels:
        #    metric_url = f'{base_url}measurements/{quote(interface)}/{label}?start=-{week*2}&step={step}'
        #    parsed_metrics = add_metrics2(metric_url, interface, parsed_metrics, auth)

    for interface in parsed_metrics:
        if 'node[' not in interface:
            parsed_metrics[interface] = average_lists(parsed_metrics[interface])
            parsed_metrics[interface]['stats'] = summary_stats(parsed_metrics, interface, metric_labels)

    parsed_metrics['node[top_n]'] = top_n_stats(parsed_metrics)
    parsed_metrics['node[device]'] = device_stats(parsed_metrics)
    parsed_metrics['node[device]'] = average_lists(parsed_metrics['node[device]'])
    parsed_metrics['node[device]']['stats'] = summary_stats(parsed_metrics, 'node[device]', metric_labels)

    end_time = time.time()
    parsed_metrics['node[data]']['elapsed'] = end_time - start_time
    parsed_metrics['node[data]']['count'] = loop_count
    print(f'Time to process {loop_count} interfaces: {end_time - start_time}')
    return parsed_metrics


def get_interfaces(url:str, auth:HTTPBasicAuth, node:str) -> dict:
    """Identify available interfaces on provided node

    Args:
        url (str): URL to OpenNMS API
        auth (HTTPBasicAuth): Authentication credentials
        node (str): Foreign source name and ID of node

    Returns:
        dict: Raw API response
    """
    data = get_data(f'{url}resources/fornode/{node}', auth=auth)
    return data


def filter_interfaces(interface_list:dict) -> list:
    """Filter out unwanted interfaces

    Args:
        interface_list (dict): All resources available on node

    Returns:
        list: List of metrics available on VIP interface
    """
    if_list = [interface for interface in interface_list['children']['resource'] if 'ltmVSStatName' in interface['stringPropertyAttributes']]
    if if_list:
        metrics = [rrd for rrd in if_list[0]['rrdGraphAttributes']]
        interfaces = [interface['id'] for interface in if_list]
    else:
        metrics = []
        interfaces = []

    return interfaces, metrics


def summary_stats(parsed_metrics:dict, interface:str, metrics:list) -> dict:
    """Calculate summary statistics for provided interface

    Args:
        parsed_metrics (dict): Collected metrics
        interface (str): Interface to generate statistics for
        metrics (list): Metrics to use for statistics

    Returns:
        dict: Dict of summary stats for provided interface
    """
    summary = {}
    raw = {}

    if interface == 'node[device]':
        raw = parsed_metrics[interface]
        for metric in metrics:
            raw[metric] = [item for item in raw[metric] if item is not None]
    else:
        for metric in metrics:
            raw[metric] = []
            for ts in parsed_metrics[interface]['ts']:
                raw[metric].append(parsed_metrics[interface]['ts'][ts].get(metric))
            raw[metric] = [item for item in raw[metric] if item is not None]

    for metric in metrics:
        summary[metric] = {}
        summary[metric]['Min'] = np.min(raw[metric] or [0])
        summary[metric]['Max'] = np.max(raw[metric] or [0])
        summary[metric]['Average'] = np.mean(raw[metric] or [0])
        summary[metric]['Total'] = np.sum(raw[metric] or [0])

    return summary
