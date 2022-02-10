# trending

from datetime import datetime
from models import Day
from ra_processing import average_metrics

def time_trend(parsed_metrics:dict, interface:str, label:list[str]=['ifOutOctets','ifInOctets']) -> dict:
    trend = {'x': [], 'y': [], 'z': [], 'c': [], 'hour':{}}
    for j in parsed_metrics[interface]['day_of_week']:
        if j != 'total':
            for k in parsed_metrics[interface]['day_of_week'][j]:
                if label[0] in parsed_metrics[interface]['day_of_week'][j][k]:
                    if parsed_metrics[interface]['day_of_week'][j][k][label[0]] != None:
                        trend['x'].append(Day(j).name)
                        if k == 'total':
                            trend['y'].append(f'average')
                        else:
                            trend['y'].append(f'{k}:00')
                        trend['z'].append(parsed_metrics[interface]['day_of_week'][j][k][label[0]])
                        trend['c'].append('Bytes Out')
                if  label[1] in parsed_metrics[interface]['day_of_week'][j][k]:
                    if parsed_metrics[interface]['day_of_week'][j][k][label[1]] != None:
                        trend['x'].append(Day(j).name)
                        if k == 'total':
                            trend['y'].append(f'average')
                        else:
                            trend['y'].append(f'{k}:00')
                        trend['z'].append(parsed_metrics[interface]['day_of_week'][j][k][label[1]])
                        trend['c'].append('Bytes In')
    for k in parsed_metrics[interface]['hour_of_day']:
        trend['hour'][k] = {'Bytes Out': [], 'Bytes In': []}
        trend['hour'][k]['Bytes Out'].append(parsed_metrics[interface]['hour_of_day'][k].get(label[0]))
        trend['hour'][k]['Bytes In'].append(parsed_metrics[interface]['hour_of_day'][k].get(label[1]))
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
