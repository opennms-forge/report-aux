# heatmap.py

from models import Day

from requests.auth import HTTPBasicAuth
from urllib.parse import quote
from datetime import datetime
import requests
import numpy as np
import collections
import time
import json

def get_data(url:str, auth:HTTPBasicAuth) -> dict:
    headers = {'Accept': 'application/json'}
    print('Getting data from: ' + url)
    data = requests.get(url, auth=auth, headers=headers)
    return data.json()


def post_data(url:str, auth:HTTPBasicAuth, payload) -> dict:
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    print(f"Getting data from: {url}/{payload['source'][0]['resourceId']}")
    data = requests.post(url, auth=auth, headers=headers, data=json.dumps(payload))
    return data.json()


def blank_histogram() -> dict:
    blank = {'ts':{}, 'summary':{}}
    blank['day_of_week'] = {0:{'total':{}}, 1:{'total':{}}, 2:{'total':{}}, 3:{'total':{}}, 4:{'total':{}}, 5:{'total':{}}, 6:{'total':{}}}
    blank['hour_of_day'] = {}
    for hour in range(0,24):
        blank['hour_of_day'][hour] = {}
        for day in range(0,7):
            blank['day_of_week'][day][hour] = {}
    return blank

def average_metrics(metrics:dict) -> dict:
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
    for ts in parsed_metrics['ts']:
        parsed_metrics['ts'][ts] = average_metrics(parsed_metrics['ts'][ts])
    for hour in range(0,24):
        parsed_metrics['hour_of_day'][hour] = average_metrics(parsed_metrics['hour_of_day'][hour])
        for day in range(0,7):
            parsed_metrics['day_of_week'][day][hour] = average_metrics(parsed_metrics['day_of_week'][day][hour])
            parsed_metrics['day_of_week'][day]['total'] = average_metrics(parsed_metrics['day_of_week'][day]['total'])
    return parsed_metrics


def add_metrics(url:str, interface:str, parsed_metrics:dict, auth:HTTPBasicAuth) -> dict:
    metric_data = get_data(url, auth=auth)

    for i in range(0, len(metric_data['timestamps'])):
        ts = metric_data['timestamps'][i]
        date = datetime.fromtimestamp(ts/1000)
        column = metric_data['columns'][0]['values'][i]
        if column == 'NaN':
            column = None
        label = metric_data['metadata']['resources'][0]['label']
        parsed_metrics[interface]['label'] = label
        if parsed_metrics[interface].get('ts'):
            if parsed_metrics[interface]['ts'].get(ts):
                parsed_metrics[interface]['ts'][ts][metric_data['labels'][0]] = column
                parsed_metrics[interface]['ts'][ts]['timestamp'] = ts
                parsed_metrics[interface]['ts'][ts]['date'] = date
                parsed_metrics[interface]['ts'][ts]['day'] = Day(date.weekday())
            else:
                parsed_metrics[interface]['ts'][ts] = {metric_data['labels'][0]: column, 'timestamp': ts, 'date': date, 'day': Day(date.weekday())}
        else:
            parsed_metrics[interface]['ts'] = {ts: {metric_data['labels'][0]: column, 'timestamp': ts, 'date': date, 'day': Day(date.weekday())}}


    return parsed_metrics


def combine_octets(parsed_metrics:dict, interface:str) -> dict:
    for ts in parsed_metrics[interface]['ts']:
        if parsed_metrics[interface]['ts'][ts].get('ifInOctets') != None and parsed_metrics[interface]['ts'][ts].get('ifOutOctets') != None:
            parsed_metrics[interface]['ts'][ts]['ifOctets'] = parsed_metrics[interface]['ts'][ts]['ifInOctets'] + parsed_metrics[interface]['ts'][ts]['ifOutOctets']
        elif parsed_metrics[interface]['ts'][ts].get('ifInOctets') != None and parsed_metrics[interface]['ts'][ts].get('ifOutOctets') == None:
            parsed_metrics[interface]['ts'][ts]['ifOctets'] = parsed_metrics[interface]['ts'][ts]['ifInOctets']
        elif parsed_metrics[interface]['ts'][ts].get('ifInOctets') == None and parsed_metrics[interface]['ts'][ts].get('ifOutOctets') != None:
            parsed_metrics[interface]['ts'][ts]['ifOctets'] = parsed_metrics[interface]['ts'][ts]['ifOutOctets']
        elif parsed_metrics[interface]['ts'][ts].get('ifInOctets') == None and parsed_metrics[interface]['ts'][ts].get('ifOutOctets') == None:
            parsed_metrics[interface]['ts'][ts]['ifOctets'] = None
    return parsed_metrics


def sort_histogram(parsed_metrics:dict, interface:str, metric:str) -> dict:
    for ts in parsed_metrics[interface]['ts']:
        if parsed_metrics[interface]['ts'][ts].get(metric):
            day = parsed_metrics[interface]['ts'][ts]['day'].value
            hour = parsed_metrics[interface]['ts'][ts]['date'].hour

            if parsed_metrics[interface]['day_of_week'][day]['total'].get(metric):
                parsed_metrics[interface]['day_of_week'][day]['total'][metric] += parsed_metrics[interface]['ts'][ts][metric]
            else:
                parsed_metrics[interface]['day_of_week'][day]['total'][metric] = parsed_metrics[interface]['ts'][ts][metric]

            if parsed_metrics[interface]['hour_of_day'][hour].get(metric):
                parsed_metrics[interface]['hour_of_day'][hour][metric] += parsed_metrics[interface]['ts'][ts][metric]
                if parsed_metrics[interface]['day_of_week'][day][hour].get(metric):
                    parsed_metrics[interface]['day_of_week'][day][hour][metric] += parsed_metrics[interface]['ts'][ts][metric]
                else:
                    parsed_metrics[interface]['day_of_week'][day][hour][metric] = parsed_metrics[interface]['ts'][ts][metric]
            else:
                parsed_metrics[interface]['hour_of_day'][hour][metric] = parsed_metrics[interface]['ts'][ts][metric]
                parsed_metrics[interface]['day_of_week'][day][hour][metric] = parsed_metrics[interface]['ts'][ts][metric]

    return parsed_metrics


def add_metrics2(url:str, interface:str, parsed_metrics:dict, auth:HTTPBasicAuth) -> dict:
    metric_data = get_data(url, auth=auth)

    for i in range(0, len(metric_data['timestamps'])):
        ts = metric_data['timestamps'][i]
        date = datetime.fromtimestamp(ts/1000)
        hour = date.hour
        day = date.weekday()
        column = metric_data['columns'][0]['values'][i]
        if column == 'NaN':
            column = None

        label = metric_data['metadata']['resources'][0]['label']
        parsed_metrics[interface]['label'] = label
        metric = metric_data['labels'][0]

        if parsed_metrics[interface]['ts'].get(ts):
            parsed_metrics[interface]['ts'][ts][metric] = column
            parsed_metrics[interface]['ts'][ts]['timestamp'] = ts
            parsed_metrics[interface]['ts'][ts]['day'] = day
        else:
            parsed_metrics[interface]['ts'][ts] = {metric: column, 'timestamp': ts, 'day': day}
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

    parsed_metrics[label]['ts'] = dict(collections.OrderedDict(sorted(parsed_metrics[label]['ts'].items())))

    return parsed_metrics


def add_metrics3(url:str, interface:str, parsed_metrics:dict, auth:HTTPBasicAuth, metrics:list, start:int, step:int=1) -> dict:
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

            label = metric_data['metadata']['resources'][z]['label']
            parsed_metrics[interface]['label'] = label
            metric = metric_data['labels'][z]

            if not parsed_metrics.get(label):
                parsed_metrics[label] = blank_histogram()

            if parsed_metrics[interface]['ts'].get(ts):
                parsed_metrics[interface]['ts'][ts][metric] = column
                parsed_metrics[interface]['ts'][ts]['timestamp'] = ts
                parsed_metrics[interface]['ts'][ts]['day'] = day
            else:
                parsed_metrics[interface]['ts'][ts] = {metric: column, 'timestamp': ts, 'day': day}

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

    parsed_metrics[label]['ts'] = dict(collections.OrderedDict(sorted(parsed_metrics[label]['ts'].items())))

    return parsed_metrics


def main(base_url:str, auth:HTTPBasicAuth, interfaces:list, rrds:list) -> dict:
    start_time = time.time()
    if rrds:
        metric_labels = rrds
    else:
        metric_labels = ['ifInOctets', 'ifOutOctets']
    parsed_metrics = {}

    minute = 60000
    hour = minute * 60
    day = hour * 24
    week = day * 7
    month = day * 30
    step = 1
    loop_count = 0

    for interface in interfaces:
        loop_count += 1
        if loop_count > 5:
            break
        parsed_metrics[interface] = {'ts':{}}

        metric_url = f'{base_url}measurements'
        parsed_metrics = add_metrics3(metric_url, interface, parsed_metrics, auth, metric_labels, week*3, step)
        #for label in metric_labels:
        #    metric_url = f'{base_url}measurements/{quote(interface)}/{label}?start=-{week*2}&step={step}'
        #    parsed_metrics = add_metrics2(metric_url, interface, parsed_metrics, auth)

    for interface in parsed_metrics:
        if 'node[' not in interface:
            parsed_metrics[interface] = average_lists(parsed_metrics[interface])

    end_time = time.time()
    print(f'Time to process {loop_count} interfaces: {end_time - start_time}')
    return parsed_metrics


def get_interfaces(base_url:str, auth:HTTPBasicAuth, node:str) -> dict:
    data = get_data(f'{base_url}resources/fornode/{node}', auth=auth)
    return data


def filter_interfaces(interface_list:dict) -> list:
    if_list = [interface for interface in interface_list['children']['resource'] if 'ltmVSStatName' in interface['stringPropertyAttributes']]
    if if_list:
        metrics = [rrd for rrd in if_list[0]['rrdGraphAttributes']]
        interfaces = [interface['id'] for interface in if_list]
    else:
        metrics = []
        interfaces = []

    return interfaces, metrics
