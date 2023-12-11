import json
import os
import datetime
import time
import requests
import faker
import click
import random
from collections import OrderedDict

fake = faker.Faker()

ENV_NAMES = ["dev", "staging", "prod"]
SERVER_NAMES = ["sparrow", "dove", "pigeon", "eagle", "hawk", "falcon"]
DATACENTERS = ["chopin", "bach", "brahms", "mozart", "beethoven", "tchaikovsky"]

METRICS_ENDPOINT = "/v0/pipes/latest_att_keys.json"

def read_tb_info():
    # Read in token from .tinyb file
    with open(os.path.expanduser('.tinyb'), 'r') as f:
        tb_info = json.load(f)
    return tb_info

def fetch_metrics():
    # Fetch the current working set of metrics and their attributes from Tinybird
    tb_info = read_tb_info()
    resp = requests.get(
        tb_info['host'] + METRICS_ENDPOINT,
        headers={'Authorization': f'Bearer {tb_info["token"]}'}
    )
    resp.raise_for_status()
    if len(resp.json()['data']) > 0:
        # Using an Ordered Dict to preserve the order of the metrics for Faker
        metrics = OrderedDict({item['id']: item['latest_att_keys'] for item in resp.json()['data']})
    else:
        metrics = OrderedDict()
    return metrics

def generate_metric(current_metrics, attribute_reuse_rate=0.5):
    # Fetches the current metrics, picks some attributes, and adds a new unique metric
    current_metric_names = current_metrics.keys()
    # Flatten the list of attributes
    flattened_values = [item for sublist in current_metrics.values() for item in sublist]
    # Get a list of unique attributes
    current_metric_attributes = list(set(flattened_values))

    new_metric_name = fake.word()
    while new_metric_name in current_metric_names:
        new_metric_name = fake.word()  # Ensure unique name
    new_metric_attributes = ["env", "server", "datacenter"]  # Have some default attributes
    # Generate some new attributes
    new_metric_attributes = new_metric_attributes + fake.words(
        nb=fake.random_int(min=1, max=5),  # Pick a random number of attributes
        unique=True
    )
    # If there are some existing metrics, pick some attributes to reuse
    if len(current_metric_attributes) > 0:
        reuse_metric_attributes = fake.random_elements(
            elements=current_metric_attributes, length=round(len(new_metric_attributes)*attribute_reuse_rate)
        )
        new_metric_attributes = new_metric_attributes + reuse_metric_attributes
    # return the new metric object with unique name and set of attributes
    return new_metric_name, list(set(new_metric_attributes))

def alphabet_position(letter):
    """Return the position of the letter in the alphabet (a=1, b=2, etc.)."""
    return ord(letter.lower()) - ord('a') + 1

def metric_value(*args):
    """Calculate a value based on the alphanumeric sum of provided attributes"""
    total = 0
    for arg in args:
        total += sum(alphabet_position(letter) for letter in arg if letter.isalpha())
    
    total *= 10  # Multiply the total by 10
    deviation = random.randint(-total * 0.1, total * 0.1)  # Deviation up to 10% of total
    return int(total + deviation)

def generate_events(metric_defs, batch_size=1):
    # Generates a batch of events over a list of metrics
    batch = []
    
    # Pre-generate random metric names, environments, and servers
    random_metric_names = [fake.random_element(elements=metric_defs.keys()) for _ in range(batch_size)]
    random_envs = [fake.random_element(elements=ENV_NAMES) for _ in range(batch_size)]
    random_servers = [fake.random_element(elements=SERVER_NAMES) for _ in range(batch_size)]
    random_datacenters = [fake.random_element(elements=DATACENTERS) for _ in range(batch_size)]
    random_colors = [fake.color_name() for _ in range(batch_size)]
    
    for i in range(batch_size):
        metric_name = random_metric_names[i]
        metric_attributes = metric_defs[metric_name]
        
        current_time = datetime.datetime.utcnow()
        ts = current_time.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        env = random_envs[i]
        server = random_servers[i]
        datacenter = random_datacenters[i]
        color = random_colors[i]
        val = str(metric_value(metric_name, env, server, datacenter))
        
        att = {att: fake.word() for att in metric_attributes}
        att['env'] = env
        att['server'] = server
        att['datacenter'] = datacenter
        att['color'] = color
        
        batch.append({"id": metric_name, "ts": ts, "val": val, "att": att})
        
    return batch

@click.command()
@click.option('--metrics', default=10, help='Number of metrics to generate')
@click.option('--batch', default=3000, help='Number of events to generate per batch cycle')
@click.option('--events', default=100000, help='Number of events to generate in total')
def runner(metrics, batch, events):
    target_metrics_count = metrics
    batch_size = batch
    total_events = events
    print(f"Generating {total_events} events across {target_metrics_count} metrics in batches of {batch_size}")
    print("Fetching existing metrics from Tinybird")
    current_metrics = fetch_metrics()
    current_metrics_count = len(current_metrics.keys())
    if current_metrics_count < target_metrics_count:
        new_metrics_count = target_metrics_count - current_metrics_count
        print(f"Only {current_metrics_count} metrics found, generating {new_metrics_count} more")
        for i in range(new_metrics_count):
            new_metric_name, new_metric_attributes = generate_metric(current_metrics)
            current_metrics[new_metric_name] = new_metric_attributes
    # update the metrics count to include new additions
    current_metrics_count = len(current_metrics.keys())
    print(f"Generating {total_events} events across {current_metrics_count} metrics in batches of {batch_size}")
    for _ in range(total_events//batch_size):
        event_batch = generate_events(current_metrics, batch_size=batch_size)
        # Post to Tinybird Datasource
        tb_info = read_tb_info()
        resp = requests.post(
            tb_info['host'] + f"/v0/events",
            params={'name': 'events', 'token': tb_info['token']},
            data='\n'.join([json.dumps(event) for event in event_batch]),
        )
        resp.raise_for_status()
        print(f"Posted {len(event_batch)} events to Tinybird")
        time.sleep(0.01)  # Ensure batches are spaced apart
    print("Competed generating events")

def generate_events_fixture(batch_size=10):
    # Generates a few very basic events for testing purposes
    batch = []
    for i in range(batch_size):
        id = "KEEPALIVE"
        current_time = datetime.datetime.utcnow()
        ts = current_time.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        val = "1"
        att = {
            "env": "dev",
            "server": "sparrow",
            "datacenter": "chopin",
            "color": "red"
        }
        batch.append({"id": id, "ts": ts, "val": val, "att": att})
        time.sleep(0.01)  # Ensure events are slightly spaced apart

    # Output as ndjson file
    with open("tinybird/datasources/fixtures/events.ndjson", "w") as f:
        for event in batch:
            f.write(json.dumps(event) + "\n")

if __name__ == '__main__':
    runner()
