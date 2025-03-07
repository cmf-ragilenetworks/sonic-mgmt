'''
Description:    This file contains the Directed Broadcast test for SONIC

Usage:          Examples of how to use log analyzer
                ptf --test-dir ptftests dir_bcast_test.BcastTest  --platform remote  -t "testbed_type='t0';router_mac='00:01:02:03:04:05';vlan_info='/root/vlan_info.txt'" --relax --debug info --log-file /tmp/dir_bcast_test.log  --disable-vxlan --disable-geneve --disable-erspan --disable-mpls --disable-nvgre

'''

#---------------------------------------------------------------------
# Global imports
#---------------------------------------------------------------------
import logging
import random
import json
import ptf
import ptf.packet as scapy
import ptf.dataplane as dataplane

from ptf import config
from ptf.base_tests import BaseTest
from ptf.mask import Mask
from ptf.testutils import *
from ipaddress import ip_address, ip_network

class BcastTest(BaseTest):
    '''
    @summary: Overview of functionality
    Test sends a directed broadcast packet on one of the non-VLAN RIF interface and destined to the
    broadcast IP of the VLAN RIF. It expects the packet to be broadcasted to all the member port of
    VLAN

    This class receives a text file containing the VLAN IP address/prefix and the member port list

    For the device configured with VLAN interface and member ports,
     - IP frame, Dst Mac = Router MAC, Dst IP = Directed Broadcast IP
    '''

    #---------------------------------------------------------------------
    # Class variables
    #---------------------------------------------------------------------
    BROADCAST_MAC = 'ff:ff:ff:ff:ff:ff'
    DHCP_SERVER_PORT = 67
    TEST_SRC_IP = "1.1.1.1"  # Some src IP

    def __init__(self):
        '''
        @summary: constructor
        '''
        BaseTest.__init__(self)
        self.test_params = test_params_get()

    #---------------------------------------------------------------------

    def setUp(self):
        self.dataplane = ptf.dataplane_instance
        self.router_mac = self.test_params['router_mac']
        ptf_test_port_map = self.test_params['ptf_test_port_map']
        with open(ptf_test_port_map) as f:
            self.ptf_test_port_map = json.load(f)
        self.src_ports = self.ptf_test_port_map['ptf_src_ports']
        self._vlan_dict = self.ptf_test_port_map['vlan_ip_port_pair']

    #---------------------------------------------------------------------

    def check_all_dir_bcast(self):
        '''
        @summary: Loop through all the VLANs and send directed broadcast packets
        '''
        for vlan_pfx, dst_ports in self._vlan_dict.items():
            if ip_network(vlan_pfx).version == 4:
                bcast_ip = str(ip_network(vlan_pfx).broadcast_address)
                logging.info("bcast_ip: {}, vlan_pfx: {}, dst_ports: {}".format(bcast_ip, vlan_pfx, dst_ports))
                self.check_ip_dir_bcast(bcast_ip, dst_ports)
                self.check_bootp_dir_bcast(bcast_ip, dst_ports)

    #---------------------------------------------------------------------

    def check_ip_dir_bcast(self, dst_bcast_ip, dst_ports):
        '''
        @summary: Check directed broadcast IP forwarding and receiving on all member ports.
        '''
        ip_src = self.TEST_SRC_IP
        ip_dst = dst_bcast_ip
        src_mac = self.dataplane.get_mac(0, 0)
        bcast_mac = self.BROADCAST_MAC

        pkt = simple_ip_packet(eth_dst=self.router_mac,
                               eth_src=src_mac,
                               ip_src=ip_src,
                               ip_dst=ip_dst)

        exp_pkt = simple_ip_packet(eth_dst=bcast_mac,
                               eth_src=self.router_mac,
                               ip_src=ip_src,
                               ip_dst=ip_dst)

        masked_exp_pkt = Mask(exp_pkt)
        masked_exp_pkt.set_do_not_care_scapy(scapy.IP, "chksum")
        masked_exp_pkt.set_do_not_care_scapy(scapy.IP, "ttl")

        src_port = random.choice([port for port in self.src_ports if port not in dst_ports])
        send_packet(self, src_port, pkt)
        logging.info("Sending packet from port " + str(src_port) + " to " + ip_dst)

        pkt_count = count_matched_packets_all_ports(self, masked_exp_pkt, dst_ports)
        '''
        Check if broadcast packet is received on all member ports of vlan
        '''
        logging.info("Received " + str(pkt_count) + " broadcast packets, expecting " + str(len(dst_ports)))
        assert (pkt_count == len(dst_ports)), "received {} expected {}".format(pkt_count, len(dst_ports))

        return

    #---------------------------------------------------------------------

    def check_bootp_dir_bcast(self, dst_bcast_ip, dst_ports):
        '''
        @summary: Check directed broadcast BOOTP packet forwarding and receiving on all member ports.
        '''
        ip_src = self.TEST_SRC_IP
        ip_dst = dst_bcast_ip
        src_mac = self.dataplane.get_mac(0, 0)
        bcast_mac = self.BROADCAST_MAC
        udp_port = self.DHCP_SERVER_PORT

        pkt = simple_udp_packet(eth_dst=self.router_mac,
                                eth_src=src_mac,
                                ip_src=ip_src,
                                ip_dst=ip_dst,
                                udp_sport=udp_port,
                                udp_dport=udp_port)

        exp_pkt = simple_udp_packet(eth_dst=bcast_mac,
                                    eth_src=self.router_mac,
                                    ip_src=ip_src,
                                    ip_dst=ip_dst,
                                    udp_sport=udp_port,
                                    udp_dport=udp_port)

        masked_exp_pkt = Mask(exp_pkt)
        masked_exp_pkt.set_do_not_care_scapy(scapy.IP, "chksum")
        masked_exp_pkt.set_do_not_care_scapy(scapy.IP, "ttl")

        src_port = random.choice([port for port in self.src_ports if port not in dst_ports])
        send_packet(self, src_port, pkt)
        logging.info("Sending BOOTP packet from port " + str(src_port) + " to " + ip_dst)

        pkt_count = count_matched_packets_all_ports(self, masked_exp_pkt, dst_ports)
        '''
        Check if broadcast BOOTP packet is received on all member ports of vlan
        '''
        logging.info("Received " + str(pkt_count) + " broadcast BOOTP packets, expecting " + str(len(dst_ports)))
        assert (pkt_count == len(dst_ports)), "received {} expected {}".format(pkt_count, len(dst_ports))

        return

    #---------------------------------------------------------------------

    def runTest(self):
        """
        @summary: Send Broadcast IP packet destined to a VLAN RIF and with unicast Dst MAC
        Expect the packet to be received on all member ports of VLAN
        """
        self.check_all_dir_bcast()
