class AnomalyClassifier:
    """Классификация типа аномалии по признакам события"""

    def classify(self, event: dict) -> str:
        bytes_val = event['bytes']
        packets  = event['packets']
        duration = event['duration']
        dst_port = event['dst_port']
        dst_ip   = event['dst_ip']
        protocol = event.get('protocol', '')

        # DDoS — огромный объём, много пакетов, очень короткая сессия
        if bytes_val > 100000 and packets > 500 and duration < 0.1:
            return 'ddos'

        # Port scan — маленький объём, мало пакетов, нестандартный порт
        if bytes_val < 200 and packets <= 3 and dst_port < 1024:
            return 'portscan'

        # Data leak — большой объём, внешний IP
        if bytes_val > 50000 and not (
            dst_ip.startswith('10.') or
            dst_ip.startswith('192.168.') or
            dst_ip.startswith('172.')
        ):
            return 'data_leak'

        # BGP аномалия — порт 179 или протокол BGP
        if dst_port == 179 or protocol == 'BGP':
            return 'bgp_anomaly'

        return 'unknown'
