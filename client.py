import json
import ssl
from google.protobuf.json_format import MessageToJson
from kafka import KafkaConsumer
import settings
import tetration_network_policy_pb2 as tet


class Stats(object):
    def __init__(self):
        self.total_contracts = 0
        self.protocols = []
        self.num_port_ranges = 0


stats = Stats()


class TetrationMessageHandler(object):
    """
    Class responsible for refreshing collecting the messages from the Kafka stream
    coming from Tetration Analytics
    """

    def __init__(self):
        # Load Kafka topic configuration for tenant
        self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        self.ssl_context.options |= ssl.OP_NO_SSLv2
        self.ssl_context.options |= ssl.OP_NO_SSLv3
        self.ssl_context.options |= ssl.OP_NO_TLSv1
        self.ssl_context.options |= ssl.OP_NO_TLSv1_1
        self.update_count = 1
        topic = open('credentials/topic.txt', 'r').read()
        brokers = open('credentials/kafkaBrokerIps.txt', 'r').read().split(',')

        print('Loading certificates...')
        # Connect to the Kafka topic
        self.ssl_context.load_cert_chain('credentials/kafkaConsumerCA.cert',
                                         'credentials/kafkaConsumerPrivateKey.key')
        print('Starting Kafka client...')
        self.kafka_client = KafkaConsumer(bootstrap_servers=brokers,
                                          security_protocol='SSL',
                                          ssl_context=self.ssl_context)
        print('Subscribing to', topic)
        self.kafka_client.subscribe(topic)

        self.update_version = 0
        self.msg_seq_num = None
        self.message_in_progress = False
        self.msg_buffer = []

    def has_update(self):
        return self.msg_buffer and not self.message_in_progress

    def handle_message(self, update):
        settings.logger.debug('handling message of type %s', update.type)
        # Check if we're in the middle of processing an update
        if self.message_in_progress:
            if self.update_version != update.version or update.sequence_num != self.msg_seq_num + 1:
                # Misordered message. Abort
                settings.logger.warning('Misordered message received. %s %s %s %s', self.update_version,
                                        update.version,
                                        update.sequence_num, self.msg_seq_num + 1)
                self.msg_buffer = []
                if update.type != tet.KafkaUpdate.UPDATE_START or update.version < self.update_version:
                    self.message_in_progress = False
                    return
                self.update_version = update.version
            # Queue the message for processing
            self.msg_buffer.append(update)
            self.msg_seq_num = update.sequence_num

            # If last message, then process it
            if update.type == tet.KafkaUpdate.UPDATE_END:
                # Process the update
                self.message_in_progress = False
                settings.logger.debug('Update queued for processing')
        else:
            # Look for a later version update beginning with a Start message
            if update.type != tet.KafkaUpdate.UPDATE_START:
                settings.logger.warning(
                    'Received a non-Start message when message not in progress')
                return
            if self.update_version > update.version:
                settings.logger.warning(
                    'Received a Start message with smaller version than previously processed')
                return
            self.update_version = update.version
            self.msg_seq_num = update.sequence_num
            self.msg_buffer = [update]
            self.message_in_progress = True
        settings.logger.debug('message %s %s in progress: %s message buffer length: %s',
                              self.update_version,
                              self.msg_seq_num,
                              self.message_in_progress,
                              len(self.msg_buffer))

    def dump_msg_buffer_to_file(self):
        json_file = open('update.json', 'w')
        for message in self.msg_buffer:
            json_file.write(json.dumps(json.loads(MessageToJson(message, preserving_proto_field_name=True,
                                                                including_default_value_fields=True)), indent=4, sort_keys=True))
        json_file.close()

    def dump_msg_buffer_to_log(self):
        update = {}
        for message in self.msg_buffer:
            if message.type == tet.KafkaUpdate.UPDATE_START:
                update['type'] = 'UPDATE_START'
            elif message.type == tet.KafkaUpdate.UPDATE:
                update['type'] = 'UPDATE'
            elif message.type == tet.KafkaUpdate.UPDATE_END:
                update['type'] = 'UPDATE_END'
            update['sequence_num'] = message.sequence_num
            update['version'] = message.version
            tenant_policy = message.tenant_network_policy
            update['tenant_network_policy'] = {}
            update['tenant_network_policy']['tenant_name'] = tenant_policy.tenant_name
            for network_policy in tenant_policy.network_policy:
                update['tenant_network_policy']['network_policies'] = []
                policy = {'inventory_filters': [], 'intents': []}
                for inventory_filter in network_policy.inventory_filters:
                    update_inventory_filter = {'id': inventory_filter.id,
                                               'inventory_items': []}
                    for inventory_item in inventory_filter.inventory_items:
                        if inventory_item.HasField('ip_address'):
                            ip_addr = ''
                            for char in inventory_item.ip_address.ip_addr:
                                ip_addr += str(char) + '.'
                            ip_addr = ip_addr[:-1]
                            update_inventory_item = {'ip_addr': ip_addr,
                                                     'prefix_length': inventory_item.ip_address.prefix_length,
                                                     'addr_family': inventory_item.ip_address.addr_family}
                            print(update_inventory_item)
                        elif inventory_item.HasField('address_range'):
                            start_ip_addr = ''
                            for char in inventory_item.address_range.start_ip_addr:
                                start_ip_addr += str(ord(char)) + '.'
                            start_ip_addr = start_ip_addr[:-1]
                            end_ip_addr = ''
                            for char in inventory_item.address_range.end_ip_addr:
                                end_ip_addr += str(ord(char)) + '.'
                            end_ip_addr = end_ip_addr[:-1]
                            update_inventory_item = {'start_ip_addr': start_ip_addr,
                                                     'end_ip_addr': end_ip_addr,
                                                     'addr_family': inventory_item.address_range.addr_family}
                        else:
                            assert False
                        update_inventory_filter['inventory_items'].append(
                            update_inventory_item)
                    policy['inventory_filters'].append(update_inventory_filter)
                for intent in network_policy.intents:
                    print(intent)
                    update_intent = {'id': intent.id}
                    if intent.action == tet.Intent.INVALID:
                        update_intent['action'] = 'INVALID'
                    elif intent.action == tet.Intent.ALLOW:
                        update_intent['action'] = 'ALLOW'
                    elif intent.action == tet.Intent.DROP:
                        update_intent['action'] = 'DROP'
                    update_intent['flow_filter'] = {'id': intent.flow_filter.id,
                                                    'consumer_filter_id': intent.flow_filter.consumer_filter_id,
                                                    'provider_filter_id': intent.flow_filter.provider_filter_id,
                                                    'protocol_and_ports': []}
                    for protocol_and_ports in intent.flow_filter.protocol_and_ports:
                        ports = {'protocol': protocol_and_ports.protocol}
                        ports['port_ranges'] = []
                        for port_range in protocol_and_ports.port_ranges:
                            ports['port_ranges'].append({'start_port': port_range.start_port,
                                                         'end_port': port_range.end_port})
                        ports['ports'] = []
                        for port in protocol_and_ports.ports:
                            ports['ports'].append(port)
                        update_intent['flow_filter']['protocol_and_ports'].append(
                            ports)
                    policy['intents'].append(update_intent)
                update['tenant_network_policy']['network_policies'].append(
                    policy)
            json_file = open('update-dump.json', 'a')
            json_file.write(json.dumps(update, indent=4, sort_keys=True))
            json_file.close()
            settings.logger.debug(update)

    def dump_msg_buffer_to_binary_file(self):
        count = 1
        for message in self.msg_buffer:
            with open('update-%s-%s.bin' % (count, self.update_count), 'w') as bin_file:
                bin_file.write(message.SerializeToString())
            count += 1

    def get_updates(self):
        print('Waiting for updates...')
        for message in self.kafka_client:
            print('Message received')
            update = tet.KafkaUpdate()
            update.ParseFromString(message.value)
            self.handle_message(update)
            if self.has_update():
                print('Update received')
                # self.dump_msg_buffer_to_binary_file()
                # self.dump_msg_buffer_to_file()
                self.dump_msg_buffer_to_log()
                self.message_in_progress = False
                self.msg_buffer = []
                self.update_count += 1


if __name__ == '__main__':
    settings.init()
    msg_handler = TetrationMessageHandler()
    msg_handler.get_updates()
