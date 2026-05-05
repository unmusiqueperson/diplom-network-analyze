import json
import time
import random
from datetime import datetime
from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

PROTOCOLS = ['TCP', 'UDP', 'ICMP']
COMMON_PORTS = [80, 443, 22, 53, 8080, 3306, 5432]

def generate_normal_event():
    return {
        'timestamp': datetime.now().isoformat(),
        'src_ip': f"192.168.{random.randint(1,10)}.{random.randint(1,254)}",
        'dst_ip': f"10.0.{random.randint(1,5)}.{random.randint(1,254)}",
        'src_port': random.randint(1024, 65535),
        'dst_port': random.choice(COMMON_PORTS),
        'protocol': random.choice(PROTOCOLS),
        'bytes': random.randint(100, 5000),
        'packets': random.randint(1, 20),
        'duration': round(random.uniform(0.1, 2.0), 3),
        'is_anomaly': 0
    }

def generate_anomaly_event():
    anomaly_type = random.choice(['ddos', 'portscan', 'data_leak'])
    event = generate_normal_event()

    if anomaly_type == 'ddos':
        event['bytes'] = random.randint(100000, 1000000)
        event['packets'] = random.randint(1000, 10000)
        event['duration'] = round(random.uniform(0.001, 0.01), 3)
    elif anomaly_type == 'portscan':
        event['dst_port'] = random.randint(1, 1024)
        event['packets'] = random.randint(1, 3)
        event['bytes'] = random.randint(40, 100)
        event['duration'] = round(random.uniform(0.001, 0.05), 3)
    elif anomaly_type == 'data_leak':
        event['bytes'] = random.randint(50000, 500000)
        event['dst_ip'] = f"185.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"

    event['is_anomaly'] = 1
    return event

print("Продюсер запущен. Отправляем события в Kafka...")
count = 0

while True:
    if random.random() < 0.05:
        event = generate_anomaly_event()
        print(f"[АНОМАЛИЯ] {event['timestamp']} | {event['src_ip']} -> {event['dst_ip']} | bytes: {event['bytes']}")
    else:
        event = generate_normal_event()

    producer.send('network-events', value=event)
    count += 1

    if count % 10 == 0:
        print(f"Отправлено событий: {count}")

    time.sleep(0.5)
