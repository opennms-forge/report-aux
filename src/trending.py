# trending

from ast import In
from re import I
import numpy as np
from datetime import datetime
from types import DynamicClassAttribute
from models import Day
from ra_processing import average_metrics

def time_trend(parsed_metrics:dict, interface:str, label:list[str]=['ifOutOctets','ifInOctets']) -> dict:
    trend = {'x': [], 'y': [], 'z': [], 'c': [], 'hour':{}}
    for i in parsed_metrics:
        if i == interface:
            #print(parsed_metrics[i]['day_of_week'])
            for j in parsed_metrics[i]['day_of_week']:
                if j != 'total':
                    for k in parsed_metrics[i]['day_of_week'][j]:
                        if parsed_metrics[i]['day_of_week'][j][k].get(label[0]):
                            trend['x'].append(Day(j).name)
                            if k == 'total':
                                trend['y'].append(f'average')
                            else:
                                trend['y'].append(f'{k}:00')
                            trend['z'].append(parsed_metrics[i]['day_of_week'][j][k][label[0]])
                            trend['c'].append('Bytes Out')
                        if parsed_metrics[i]['day_of_week'][j][k].get(label[1]):
                            trend['x'].append(Day(j).name)
                            if k == 'total':
                                trend['y'].append(f'average')
                            else:
                                trend['y'].append(f'{k}:00')
                            trend['z'].append(parsed_metrics[i]['day_of_week'][j][k][label[1]])
                            trend['c'].append('Bytes In')
            for k in parsed_metrics[i]['hour_of_day']:
                trend['hour'][k] = {'Bytes Out': [], 'Bytes In': []}
                trend['hour'][k]['Bytes Out'].append(parsed_metrics[i]['hour_of_day'][k].get(label[0]))
                trend['hour'][k]['Bytes In'].append(parsed_metrics[i]['hour_of_day'][k].get(label[1]))
            for k in parsed_metrics[i]['hour_of_day']:
                trend['hour'][k] = average_metrics(trend['hour'][k])
            for k in trend['hour']:
                for metric in trend['hour'][k]:
                    if trend['hour'][k].get(metric):
                        trend['x'].append('Average')
                        trend['y'].append(f'{k}:00')
                        trend['z'].append(trend['hour'][k][metric])
                        trend['c'].append(metric)
        if len(trend['x']) >= 100:
            break
    return trend


def find_weekends(parsed_metrics:dict, interface:str) -> list:
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


def time_lines(parsed_metrics:dict, interface:str, label:list[str]=['ifOutOctets','ifInOctets']) -> dict:
    stats = {'x': [], 'y': []}
    stats2 = {'x': [], 'y': []}
    for i in parsed_metrics:
        if i == interface:
            #print(parsed_metrics[i]['day_of_week'])
            for j in parsed_metrics[i]['ts']:
                date = datetime.fromtimestamp(j/1000)
                stats['x'].append(date)
                stats2['x'].append(date)
                if parsed_metrics[i]['ts'][j][label[0]] not in [None, [None]]:
                    stats['y'].append(parsed_metrics[i]['ts'][j].get(label[0]))
                else:
                    stats['y'].append(0)
                if parsed_metrics[i]['ts'][j].get(label[1]) not in [None, [None]]:
                    stats2['y'].append(parsed_metrics[i]['ts'][j].get(label[1]) * -1)
                else:
                    stats2['y'].append(0)
                #stats['c'].append('BytesOut')
                #stats['c'].append('BytesIn')
        if len(stats['x']) >= 100:
            break
    return stats, stats2


def summary_stats(parsed_metrics:dict, interface:str, metrics:list) -> dict:
    summary = {}
    raw = {}

    if interface == 'node[device]':
        raw = parsed_metrics[interface]
    else:
        for metric in metrics:
            raw[metric] = []
            for ts in parsed_metrics[interface]['ts']:
                raw[metric].append(parsed_metrics[interface]['ts'][ts].get(metric))
            raw[metric] = [item for item in raw[metric] if item is not None]

    for metric in metrics:
        summary[metric] = {}
        summary[metric]['Min'] = np.min(raw[metric])
        summary[metric]['Max'] = np.max(raw[metric])
        summary[metric]['Average'] = np.mean(raw[metric])
        summary[metric]['Total'] = np.sum(raw[metric])

    return summary
